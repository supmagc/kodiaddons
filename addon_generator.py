# *
# *  Copyright (C) 2012-2013 Garrett Brown
# *  Copyright (C) 2010      j48antialias
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with XBMC; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# *  Based on code by j48antialias:
# *  https://anarchintosh-projects.googlecode.com/files/addons_xml_generator.py
import subprocess
import xml.etree.ElementTree
import os
import sys
import ftputil
from git import Repo, RemoteProgress
from zipfile import ZipFile
from shutil import copytree, ignore_patterns, rmtree

g_ssh = "C:\Program Files (x86)\PuTTY\plink.exe";
g_sshkey = "D:\Jelle\Documents\Ssh\github.ppk"
g_projects = [] #'plugin.video.netflixbmc']
 
# Compatibility with 3.0, 3.1 and 3.2 not supporting u"" literals
if sys.version < '3':
    import codecs
    def u(x):
        return codecs.unicode_escape_decode(x)[0]
else:
    def u(x):
        return x
    
class MyProgressPrinter(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print(op_code, cur_count, max_count, cur_count / (max_count or 100.0), message or "NO MESSAGE")
     
class Generator:
    """
        Generates a new addons.xml file from each addons addon.xml file
        and a new addons.xml.md5 hash file. Must be run from the root of
        the checked-out repo. Only handles single depth folder structure.
    """
    def __init__( self ):
        # generate files
        self._copy_projects()
        self._generate_addons_file()
        self._generate_md5_file()
        self._generate_zip_file()
        self._package_addons()
        #self._git_commit_push()
        # notify user
        print("Finished updating addons xml and md5 files")
        
    def _copy_projects( self ):
        for project in g_projects:
            _path = os.path.join(os.getcwd(), '..', project)
            if(not os.path.isdir(_path)): continue
            if(os.path.exists(project) and os.path.isdir(project)): rmtree(project)
            copytree(_path, project, ignore=ignore_patterns('.*'))     
        return
 
    def _generate_addons_file( self ):
        # addon list
        addons = os.listdir( "." )
        # final addons text
        addons_xml = u("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<addons>\n")
        # loop thru and add each addons addon.xml file
        for addon in addons:
            try:
                # skip any file or .svn folder or .git folder
                if ( not os.path.isdir( addon ) or addon.startswith('.') ): continue
                # create path
                _path = os.path.join( addon, "addon.xml" )
                # split lines for stripping
                xml_lines = open( _path, "r").read().splitlines()
                # new addon
                addon_xml = ""
                # loop thru cleaning each line
                for line in xml_lines:
                    # skip encoding format line
                    if ( line.find( "<?xml" ) >= 0 ): continue
                    # add line
                    if sys.version < '3':
                        addon_xml += unicode( line.rstrip() + "\n", "UTF-8" )
                    else:
                        addon_xml += line.rstrip() + "\n"
                # we succeeded so add to our final addons.xml text
                addons_xml += addon_xml.rstrip() + "\n\n"
            except Exception as e:
                # missing or poorly formatted addon.xml
                print("Excluding %s for %s" % ( _path, e ))
        # clean and add closing tag
        addons_xml = addons_xml.strip() + u("\n</addons>\n")
        # save file
        self._save_file( addons_xml.encode( "UTF-8" ), file="addons.xml" )
 
    def _generate_md5_file( self ):
        # create a new md5 hash
        try:
            import md5
            m = md5.new( open( "addons.xml", "r" ).read() ).hexdigest()
        except ImportError:
            import hashlib
            m = hashlib.md5( open( "addons.xml", "r", encoding="UTF-8" ).read().encode( "UTF-8" ) ).hexdigest()
 
        # save file
        try:
            self._save_file( m.encode( "UTF-8" ), file="addons.xml.md5" )
        except Exception as e:
            # oops
            print("An error occurred creating addons.xml.md5 file!\n%s" % e)
 
    def _generate_zip_file(self):
        with ZipFile('repository.supmagc.zip', 'w') as _zip:
            _path = os.path.join('repository.supmagc', 'addon.xml')
            _zip.write(_path)
 
    def _save_file( self, data, file ):
        try:
            # write data to the file (use b for Python 3)
            open( file, "wb" ).write( data )
        except Exception as e:
            # oops
            print("An error occurred saving %s file!\n%s" % ( file, e ))
            
    def _get_plugin_version(self, addon):
        addon_xml = os.path.join(addon, 'addon.xml') 
        try:
            data = open(addon_xml, 'r').read()
            node = xml.etree.ElementTree.XML(data)
            return(node.get('version'))
        except Exception as e:
            print 'Failed to open %s' % addon_xml
            print e.message
            
    def _package_addons(self):
        print "Starting to generate addon zip files"
        # addon list
        addons = os.listdir( "." )
        for addon in addons:
            # skip any file or .svn folder or .git folder
            if ( not os.path.isdir( addon ) or addon.startswith('.') ): continue
            
            version = self._get_plugin_version(addon)
            if not version:
                return
            with ZipFile(addon + os.sep + addon + '-' + version + '.zip', 'w') as addon_zip:
                for root, dirs, files in os.walk(addon):
                    for file_path in files:
                        if file_path.endswith('.zip'):
                            continue
                        print "adding %s" % os.path.join(root, file_path) 
                        addon_zip.write(os.path.join(root, file_path))
                addon_zip.close()
                
    def _git_commit_push(self):
        print "Adding, comitting and pushing content online."
        repo = Repo(".")
        assert not repo.bare
        
        git = repo.git
        command = "\"%s\" -i \"%s\"" % (g_ssh, g_sshkey)
        print "Ssh: " + command
        git.custom_environment(GIT_SSH=g_ssh)
        git.custom_environment(GIT_SSH_COMMAND=command)
        print git.checkout('master')
        
        # index = repo.index
        # print index.add(".")
        #for en in index.entries:
        #    print en
        #print index.commit("Automatically generated commit")
        #print git.add("-A")
        
        origin = repo.remotes.origin
        assert origin.exists()
        print origin.fetch(progress=MyProgressPrinter())
        print origin.push(progress=MyProgressPrinter())
 
if ( __name__ == "__main__" ):
    # start
    Generator()