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
from git import Repo, RemoteProgress
from zipfile import ZipFile
from shutil import copytree, ignore_patterns, rmtree

g_ssh = "C:\Program Files (x86)\PuTTY\plink.exe"
g_sshkey = "D:\Jelle\Documents\Ssh\github.ppk"
g_projects = []  # 'plugin.video.netflixbmc']

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

    def __init__(self):
        self.addons = []

        # self._git_pull_submodules()
        self._detect_projects()
        self._generate_addons_file()
        self._generate_md5_file()
        #self._generate_zip_file()
        self._package_addons()
        # self._git_commit_push()
        # notify user
        print("Finished updating addons xml and md5 files")

    def _get_addons_xml_path(self):
        return os.path.join(os.getcwd(), "addons.xml")

    def _load_file(self, file):
        try:
            return open(file, "r").read()
        except Exception as e:
            print "An error occurred loading {0} file!\n{1}" % (file, e)

    def _save_file(self, data, file):
        try:
            open(file, "wb").write(data)
        except Exception as e:
            print "An error occurred saving {0} file!\n{1}" % (file, e)

    def _detect_projects(self):
        root_directory = os.getcwd()
        sub_directories = os.listdir(root_directory)
        for sub_directory in sub_directories:
            path = os.path.join(root_directory, sub_directory)
            if not sub_directory.startswith(".") and os.path.isdir(path):
                print "Detected addon {0} in {1}".format(sub_directory, path)
                self.addons.append({
                    'name': sub_directory,
                    'path': path
                })
        pass

    def _generate_addons_file(self):
        # final addons text
        addons_xml = u("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<addons>\n")

        # loop thru and add each addons addon.xml file
        for addon in self.addons:
            try:
                # create path
                addon_xml_path = os.path.join(addon['path'], "addon.xml")
                # split lines for stripping
                xml_lines = self._load_file(addon_xml_path).splitlines()
                # new addon
                addon_xml = ""
                # loop thru cleaning each line
                for line in xml_lines:
                    # skip encoding format line
                    if line.find("<?xml") >= 0: continue
                    # add line
                    if sys.version < '3':
                        addon_xml += unicode(line.rstrip() + "\n", "UTF-8")
                    else:
                        addon_xml += line.rstrip() + "\n"
                # we succeeded so add to our final addons.xml text
                addons_xml += addon_xml.rstrip() + "\n\n"
            except Exception as e:
                print "Excluding {0} for {1}".format(addon_xml_path, e)

        # clean and add closing tag
        addons_xml = addons_xml.strip() + u("\n</addons>\n")

        # save file
        addons_xml_path = self._get_addons_xml_path()
        try:
            self._save_file(addons_xml.encode("UTF-8"), file=addons_xml_path)
            print "Wrote addons list to {0}".format(addons_xml_path)
        except Exception as e:
            print "An error occurred creating {0} file!\n{1}".format(addons_xml_path, e)

    def _generate_md5_file(self):
        # create a new md5 hash
        import hashlib
        addons_xml_path = self._get_addons_xml_path()
        addons_xml_md5_path = addons_xml_path + ".md5"
        m = hashlib.md5(self._load_file(addons_xml_path).encode("UTF-8")).hexdigest()

        # save file
        try:
            self._save_file(m.encode("UTF-8"), file=addons_xml_md5_path)
            print "Wrote addons md5 for {0} to {1}".format(addons_xml_path, addons_xml_md5_path)
        except Exception as e:
            print "An error occurred creating {0} file!\n{1}".format(addons_xml_md5_path, e)

    def _get_plugin_version(self, addon):
        addon_xml = os.path.join(addon['path'], 'addon.xml')
        try:
            data = open(addon_xml, 'r').read()
            node = xml.etree.ElementTree.XML(data)
            return node.get('version')
        except Exception as e:
            print 'Failed to open {0} to extract version\n{1}'.format(addon_xml, e)

    def _package_addons(self):
        for addon in self.addons:
            addon_path = addon['path']
            version = self._get_plugin_version(addon)
            zip_path = os.path.join(addon_path, addon['name'] + '-' + version + '.zip')
            with ZipFile(zip_path, 'w') as addon_zip:
                for root, dirs, files in os.walk(addon_path):
                    for file_path in files:
                        if file_path.endswith('.zip'):
                            continue
                        print "Adding {0} to {1}".format(os.path.join(addon_path, file_path), zip_path)
                        addon_zip.write(os.path.join(root, file_path))
                addon_zip.close()
                print "Merged addon {0} into {1}".format(addon['name'], zip_path)

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
        # for en in index.entries:
        #    print en
        # print index.commit("Automatically generated commit")
        # print git.add("-A")

        origin = repo.remotes.origin
        assert origin.exists()
        print origin.fetch(progress=MyProgressPrinter())
        print origin.push(progress=MyProgressPrinter())


if (__name__ == "__main__"):
    # start
    Generator()
