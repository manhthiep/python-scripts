#!/usr/bin/env python
 
import sys
import signal
import os
import errno
import getopt

from re import match, split
from subprocess import check_output
from subprocess import check_call
from debian.deb822 import Deb822
 
package_nodes = {}
package_info = {}
package_cache = []

DEBUG = False
VERBOSE = False
NO_DEPENDS = False

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
            if VERBOSE:
                print "Get package info: " + pkg_name
            pkg_node = PackageNode(pkg_name)
            package_nodes[pkg_name] = pkg_node
            # add node properties:
            pkg_node.version = pkg_info.get('Version', '')
            source = pkg_info.get('Source', '')
            if source == '':
                # source_pkg_name == pkg_name
                pkg_node.source = pkg_name
                if VERBOSE:
                    print "  Getting source package: '%s' for '%s'" % (pkg_name, pkg_name)
            else:
                # source_pkg_name != pkg_name
                pkg_node.source = match('(\S*)', source.strip()).groups()[0]
                if VERBOSE:
                    print "  Getting source package: '%s' instead of '%s'" % (pkg_node.source, pkg_name)
            if not NO_DEPENDS:
                depends = pkg_info.get('Depends', '')
                depends = get_sanitised_depends_list(depends)
                depends = sorted(depends)
                if DEBUG:
                    print "  Depends: " + ', '.join(depends)
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
    """Get source for a package"""

    source_pkg_name = ''
    pkg_node = get_node_for_package(pkg_name)
    if pkg_node:
        source_pkg_name = pkg_node.source
    else:
        print "Skip invalid package name: '%s'" % pkg_name
        source_pkg_name = ''

    return source_pkg_name

def get_source_for_package_and_depends(pkg_name):
    """Get sources for a package and its depends"""

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

def ask_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

def signal_handler(signal, frame):
    sys.exit(0)

def usage(script_name):
    print "Usage: %s [OPTIONS] PACKAGE_NAMES" % script_name
    print "Options:"
    print "  --no-depends"
    print "  --debug"
    print "  --verbose"
    print ""

if __name__ == '__main__':

    signal.signal(signal.SIGINT, signal_handler)

    if len(sys.argv) == 1:
        print "Missing arguments"
        usage(sys.argv[0])
        sys.exit(1)

    try:
        opts, packages = getopt.getopt(sys.argv[1:], '', ['no-depends', 'debug', 'verbose'])
    except getopt.GetoptError as err:
        print str(err) # will print something like "option -a not recognized"
        usage(sys.argv[0])
        sys.exit(2)

    if len(packages) == 0:
        print "Missing package names"
        usage(sys.argv[0])
        sys.exit(3)

    DEBUG = False
    VERBOSE = False
    NO_DEPENDS = False
    for o, a in opts:
        if o == "--no-depends":
            NO_DEPENDS = True
        elif o == "--debug":
            DEBUG = True
            VERBOSE = True
        elif o == "--verbose":
            VERBOSE = True

    # packages = sys.argv[1:]
    # packages = [ 'ubuntu-desktop' ]
    # print "Packages: "  + ', '.join(packages)

    n = 0
    for pkg_name in packages:
        print "Package: " + pkg_name

        if NO_DEPENDS:
            source_pkgs = [get_source_for_package(pkg_name)]
        else:
            source_pkgs = get_source_for_package_and_depends(pkg_name)
        if len(source_pkgs) > 0:
            print ""
            print "Packages to download (%d packages):" % len(source_pkgs)
            print ', '.join(source_pkgs)
            print ""
            answer = ask_yes_no("Continue to download ?")
            if answer:
                count = 0
                for source in sorted(source_pkgs):
                    count = count + 1
                    print ""
                    print "Downloading %s (%d / %d)" % (source, count, len(source_pkgs))
                    result = 0
                    result = download_source_package(source)
                    if result != 0:
                        sys.exit(result)
            else:
                print "Skip downloading source(s) for package '%s'" % pkg_name

        n += 1
        if n % 10 == 0:
            print "%d / /%d" % (n, len(packages))
