#!/usr/bin/env python
 
import sys
import signal
import os
import errno

from re import match, split
from subprocess import check_output
from subprocess import check_call
from debian.deb822 import Deb822
 
package_nodes = {}
package_info = {}
package_cache = []

class PackageNode:

    def __init__(self, pkg_name):
        self.name = pkg_name
        self.depends = {}
        self.source = ''
        self.version = ''

    def getDepends(self):
        return self.depends

    def addDepend(self, depend_name, depend_node):
        if depend_name not in self.depends:
            self.depends[depend_name] = depend_node

def download_source_package(source_pkg_name, source_pkg_version=''):
    """Download source of package"""
    result = 0

    current_dir = os.getcwd()
    if not os.path.exists(source_pkg_name):
        os.makedirs(source_pkg_name)
    os.chdir(source_pkg_name)

    try:
        if source_pkg_version == '':
            result = check_call(['apt-get','source',source_pkg_name])
        else:
            result = check_call(['apt-get','source',source_pkg_name + '=' + source_pkg_version])
    except:
        print "Unable to download source for package: '%s'" % source_pkg_name
        os.chdir(current_dir)
        return 1

    os.chdir(current_dir)
    return result

def get_package_info(pkg_name):
    """Get a dict-like object containing information for a specified package."""
    global package_info
    if pkg_name in package_info:
        return package_info.get(pkg_name)
    else:
        try:
            yaml_stream = check_output(['apt-cache','show',pkg_name])
        except:
            print "Unable to find info for package: '%s'" % pkg_name
            package_info[pkg_name] = {}
            return {}
        d = Deb822(yaml_stream)
        package_info[pkg_name] = d
        return d

def get_sanitised_depends_list(depends_string):
    """Given a Depends string, return a list of package names. Versions are
    stripped, and alternatives are all shown.
 
    """
    if depends_string == '':
        return []
    parts = split('[,\|]', depends_string)
    return [ match('(\S*)', p.strip()).groups()[0] for p in parts]
 
def get_node_for_package(pkg_name):
    """Given a package name, return the node for that package. If the
    node does not exist, it is created, and it's meta-data filled.
    """
    global package_nodes
 
    if pkg_name not in package_nodes.keys():
        pkg_info = get_package_info(pkg_name)
        if pkg_info:
            pkg_node = PackageNode(pkg_name)
            package_nodes[pkg_name] = pkg_node
            # add node properties:
            pkg_node.source = pkg_info.get('Source', '')
            pkg_node.version = pkg_info.get('Version', '')
            depends = pkg_info.get('Depends', '')
            depends = get_sanitised_depends_list(depends)
            for dep in depends:
                dep_node = get_node_for_package(dep)
                pkg_node.addDepend(dep, dep_node)
            return pkg_node
        else:
            return None
    else:
        return package_nodes.get(pkg_name)

def get_depends(pkg_name):
    """Get depends list of package and its depends and so on."""

    global package_cache
    package_cache.append(pkg_name)

    depends_list = []
    pkg_node = get_node_for_package(pkg_name)
    if pkg_node:
        depends = pkg_node.getDepends()
        for dep_name in sorted(depends.keys()):
            dep_node = depends[dep_name]
            if dep_name not in package_cache:
                depends_list.append(dep_name)
                dep_depends = get_depends(dep_name)
                depends_list = depends_list + dep_depends

    return depends_list

def get_source_for_package(pkg_name):
    """Get source package for a package"""

    source_pkg_name = ''
    pkg_node = get_node_for_package(pkg_name)
    if pkg_node:
        if pkg_node.source == '':
            # source_pkg_name == pkg_name
            source_pkg_name = pkg_name
            print "Getting source package: '%s' for '%s'" % (pkg_name, pkg_name)
        else:
            # source_pkg_name != pkg_name
            # source_pkg_name = pkg_node.source
            source_pkg_name = match('(\S*)', pkg_node.source.strip()).groups()[0]
            print "Getting source package: '%s' instead of '%s'" % (source_pkg_name, pkg_name)
    else:
        print "Invalid package name: '%s'" % pkg_name
        source_pkg_name = ''

    return source_pkg_name

def get_source_for_package_and_depends(pkg_name):

    source_pkgs = []
    
    source_pkg_name = get_source_for_package(pkg_name)
    if source_pkg_name != '':
        source_pkgs.append(source_pkg_name)

    depends = get_depends(pkg_name)
    for dep_name in sorted(depends):
        dep_source_pkg_name = get_source_for_package(dep_name)
        if dep_source_pkg_name != '' and dep_source_pkg_name not in source_pkgs:
            source_pkgs.append(dep_source_pkg_name)

    return source_pkgs

def signal_handler(signal, frame):
    sys.exit(0)

if __name__ == '__main__':

    signal.signal(signal.SIGINT, signal_handler)

    if len(sys.argv) == 1:
        print "Missing package names"
        sys.exit(1)

    packages = sys.argv[1:]
    # packages = [ 'ubuntu-desktop' ]
    # print "Packages: "  + ', '.join(packages)

    n = 0
    for pkg_name in packages:
        print "Package: " + pkg_name

        source_pkgs = get_source_for_package_and_depends(pkg_name)
        for source in sorted(source_pkgs):
            print ""
            print "Downloading " + source
            result = 0
            result = download_source_package(source)
            if result != 0:
                sys.exit(result)

        n += 1
        if n % 10 == 0:
            print "%d / /%d" % (n, len(packages))
