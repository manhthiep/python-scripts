#!/usr/bin/env python
 
import sys
from re import match, split
from subprocess import check_output
from debian.deb822 import Deb822
 
package_nodes = {}
package_info = {}
package_cache = []

class PackageNode:
    depends = {}

    def __init__(self, pkg_name):
        self.name = pkg_name
        self.depends = {}

    def getDepends(self):
        return self.depends

    def addDepend(self, depend_name, depend_node):
        if depend_name not in self.depends:
            self.depends[depend_name] = depend_node
  
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
        pkg_node = PackageNode(pkg_name)
        package_nodes[pkg_name] = pkg_node
        # add node properties:
        pkg_info = get_package_info(pkg_name)
        if pkg_info:
            depends = pkg_info.get('Depends', '')
            depends = get_sanitised_depends_list(depends)
            for dep in depends:
                dep_node = get_node_for_package(dep)
                pkg_node.addDepend(dep, dep_node)
        return pkg_node
    else:
        return package_nodes.get(pkg_name)

def print_depends_tree(pkg_name, indent=1, indent_str="  "):
    """Print depends tree"""

    global package_cache
    package_cache.append(pkg_name)
    pkg_node = get_node_for_package(pkg_name)

    depends = pkg_node.getDepends()
    for dep_name in sorted(depends.keys()):
        dep_node = depends[dep_name]
        dep_out = ""
        indent_count = 0
        while (indent_count < indent):
            dep_out = dep_out + indent_str
            indent_count = indent_count + 1
        dep_out = dep_out + dep_name
        print dep_out + depends.count
        if dep_name not in package_cache:
            print_depends_tree(dep_name, indent+1, indent_str)

def get_depends(pkg_name):
    """Get depends list of package and its depends and so on."""

    global package_cache
    package_cache.append(pkg_name)

    depends_list = []
    pkg_node = get_node_for_package(pkg_name)

    depends = pkg_node.getDepends()
    for dep_name in sorted(depends.keys()):
        dep_node = depends[dep_name]
        if dep_name not in package_cache:
            depends_list.append(dep_name)
            dep_depends = get_depends(dep_name)
            depends_list = depends_list + dep_depends

    return depends_list

def print_depends(pkg_name):
    """Print depends list"""

    depends = get_depends(pkg_name)
    for dep_name in sorted(depends):
        print "  " + dep_name

if __name__ == '__main__':

    if len(sys.argv) == 1:
        print "Missing package names"
        sys.exit(1)

    packages = sys.argv[1:]
    # packages = [ 'ubuntu-desktop' ]
    print "Packages: "  + ', '.join(packages)

    n = 0
    for pkg_name in packages:
        print "Package: " + pkg_name
        # print_depends_tree(pkg_name)
        print_depends(pkg_name)
        n += 1
        if n % 10 == 0:
            print "%d / /%d" % (n, len(packages))
