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
from shutil import copytree, ignore_patterns, rmtree, copyfile

# Compatibility with 3.0, 3.1 and 3.2 not supporting u"" literals
if sys.version < '3':
    import codecs

    def u(x):
        return codecs.unicode_escape_decode(x)[0]
else:
    def u(x):
        return x

# g_ssh = u('C:\\Program Files (x86)\\PuTTY\\plink.exe')
# g_sshkey = u('C:\\Users\\supma\\OneDrive\\Ssh\\github.ppk')

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

        self._git_pull_submodules()
        self._detect_projects()
        self._pack_textures()
        self._generate_addons_file()
        self._generate_md5_file()
        self._package_addons()
        self._copy_assets()
        self._git_commit_push()

    def _get_src_root_path(self):
        return os.path.join(os.getcwd(), "src")

    def _get_addon_root_path(self, addon):
        return os.path.join(addon['path'])

    def _get_addon_xml_path(self, addon):
        return os.path.join(self._get_addon_root_path(addon), "addon.xml")

    def _get_addons_xml_path(self):
        return os.path.join(os.getcwd(), "addons.xml")

    def _get_addons_xml_md5_path(self):
        return os.path.join(os.getcwd(), "addons.xml.md5")

    def _get_zip_dir(self, addon):
        return os.path.join(os.getcwd(), addon['name'])

    def _get_zip_path(self, addon, version):
        return os.path.join(self._get_zip_dir(addon), addon['name'] + '-' + version + '.zip')

    def _load_file(self, file):
        try:
            return open(file, mode="r", encoding='utf-8').read()
        except Exception as e:
            print('An error occurred loading {0} file!\n{1}'.format(file, e))

    def _save_file(self, data, file):
        try:
            open(file, mode="w", encoding='utf-8').write(data)
        except Exception as e:
            print('An error occurred saving {0} file!\n{1}'.format(file, e))

    def _git_add_file(self, path, message):
        repo = Repo(os.getcwd())
        assert not repo.bare
        index = repo.index

        rel_path = os.path.relpath(path).replace("\\", "/")
        print(os.getcwd() + " " + path + " >> " + rel_path)

        entry = (rel_path, 0) in index.entries
        diff = index.diff(None, paths=rel_path)

        if not entry or (len(diff) and not diff[0].deleted_file):
            print('--> Added for commit ' + message)
            repo.git.add(rel_path)
            repo.git.commit(m=message)

    def _git_pull_submodules(self):
        repo = Repo(os.getcwd())
        assert not repo.bare

        origin = repo.remotes.origin
        assert origin.exists()

        print('Fetching and pulling kodiaddons repo on master.')
        origin.fetch()
        origin.pull()
        repo.heads.master.checkout()

        submodules = repo.submodules
        for submodule in submodules:
            assert submodule.module_exists()
            assert submodule.exists()

            module = submodule.module()
            print('Found submodule {0} on {1}'.format(submodule.name, submodule.branch))

            module.remotes.origin.pull(submodule.branch)
            #submodule.update(init=True, to_latest_revision=True)
            self._git_add_file(submodule.path, 'Updated {0} on branch {1} to latest version'.format(submodule.name, submodule.branch))
            pass

        pass

    def _detect_projects(self):
        root_directory = self._get_src_root_path()
        sub_directories = os.listdir(root_directory)
        for sub_directory in sub_directories:
            path = os.path.join(root_directory, sub_directory)
            if not sub_directory.startswith(".") and os.path.isdir(path):
                print('Detected addon {0} in {1}'.format(sub_directory, path))
                self.addons.append({
                    'name': sub_directory,
                    'path': path
                })
        pass

    def _pack_textures(self):
        for addon in self.addons:
            if os.path.exists(os.path.join(self._get_addon_root_path(addon), 'media')):
                subprocess.run(['TexturePacker', '-dupecheck', '-input', 'media\\', '-output', 'media\\Textures.xbt'], cwd=self._get_addon_root_path(addon))
            if os.path.exists(os.path.join(self._get_addon_root_path(addon), 'src')):
                subprocess.run(['TexturePacker', '-dupecheck', '-input', 'src\\', '-output', 'resources\\Textures.xbt'], cwd=self._get_addon_root_path(addon))
        pass        

    def _generate_addons_file(self):
        # final addons text
        addons_xml = u("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<addons>\n")

        # loop thru and add each addons addon.xml file
        for addon in self.addons:
            try:
                # create path
                addon_xml_path = self._get_addon_xml_path(addon)
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
                        addon_xml += u(line.rstrip() + "\n", "UTF-8")
                    else:
                        addon_xml += line.rstrip() + "\n"
                # we succeeded so add to our final addons.xml text
                addons_xml += addon_xml.rstrip() + "\n\n"
            except Exception as e:
                print('Excluding {0} for {1}'.format(addon_xml_path, e))

        # clean and add closing tag
        addons_xml = addons_xml.strip() + u("\n</addons>\n")

        # save file
        addons_xml_path = self._get_addons_xml_path()
        try:
            self._save_file(addons_xml, file=addons_xml_path)
            self._git_add_file(addons_xml_path, "Newly generated addons.xml")
            print('Wrote addons list to {0}'.format(addons_xml_path))
        except Exception as e:
            print('An error occurred creating {0} file!\n{1}'.format(addons_xml_path, e))

    def _generate_md5_file(self):
        # create a new md5 hash
        import hashlib
        addons_xml_path = self._get_addons_xml_path()
        addons_xml_md5_path = self._get_addons_xml_md5_path()
        m = hashlib.md5(self._load_file(addons_xml_path).encode('utf-8')).hexdigest()

        # save file
        try:
            self._save_file(m, file=addons_xml_md5_path)
            self._git_add_file(addons_xml_md5_path, "Newly generated addons.xml.md5")
            print('Wrote addons md5 for {0} to {1}'.format(addons_xml_path, addons_xml_md5_path))
        except Exception as e:
            print('An error occurred creating {0} file!\n{1}'.format(addons_xml_md5_path, e))

    def _get_plugin_elmenttree(self, addon):
        addon_xml = self._get_addon_xml_path(addon)
        try:
            data = open(addon_xml, 'r').read()
            return xml.etree.ElementTree.fromstring(data)
        except Exception as e:
            print('Failed to open {0}'.format(addon_xml))

    def _get_plugin_version(self, addon):
        return self._get_plugin_elmenttree(addon).get('version')

    def _get_plugin_icon(self, addon):
        element = self._get_plugin_elmenttree(addon).find('.//assets/icon')
        return element.text if element != None else None

    def _get_plugin_fanart(self, addon):
        element = self._get_plugin_elmenttree(addon).find('.//assets/fanart')
        return element.text if element != None else None

    def _package_addons(self):
        for addon in self.addons:
            addon_name = addon['name']
            addon_path = addon['path']
            version = self._get_plugin_version(addon)
            zip_path = self._get_zip_path(addon, version)
            zip_path_parent = os.path.dirname(zip_path)

            if not os.path.exists(zip_path_parent):
                os.mkdir(zip_path_parent)

            with ZipFile(zip_path, 'w') as addon_zip:
                for root, dirs, files in os.walk(addon_path):
                    rel_path = os.path.relpath(root, addon_path)
                    if rel_path == ".": rel_path = ""
                    root_zip_path = os.path.join(addon_name, rel_path)
                    if rel_path.startswith('src'):
                        continue
                    addon_zip.write(root, root_zip_path)
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        file_zip_path = os.path.join(root_zip_path, file_name)
                        if (
                            file_name.endswith('.zip') or 
                            file_name.startswith(".") or 
                            (rel_path.startswith('media') and (file_name.endswith('.jpg') or file_name.endswith('.png')))
                        ):
                            continue
                        print('Adding {0} as {1} to {2}'.format(file_path, file_zip_path, zip_path))
                        addon_zip.write(file_path, file_zip_path)
                addon_zip.close()
                self._git_add_file(zip_path, 'Generated zip file for {0} at {1}'.format(addon_name, version))
                print('Merged addon {0} into {1}'.format(addon['name'], zip_path))

    def _copy_assets(self):
        for addon in self.addons:
            addon_name = addon['name']
            addon_path = addon['path']
            addon_zip_dir = self._get_zip_dir(addon)
            icon = self._get_plugin_icon(addon)
            if icon:
                icon_target = os.path.join(addon_zip_dir, icon)
                if not os.path.exists(os.path.dirname(icon_target)):
                    os.makedirs(os.path.dirname(icon_target))
                copyfile(os.path.join(addon_path, icon), icon_target)
                self._git_add_file(icon_target, 'Copied icon for {0}'.format(addon_name))
            fanart = self._get_plugin_fanart(addon)
            if fanart:
                fanart_target = os.path.join(addon_zip_dir, fanart)
                if not os.path.exists(os.path.dirname(fanart_target)):
                    os.makedirs(os.path.dirname(fanart_target))
                copyfile(os.path.join(addon_path, fanart), fanart_target)
                self._git_add_file(fanart_target, 'Copied fanart for {0}'.format(addon_name))


    def _git_commit_push(self):
        repo = Repo(os.getcwd())
        assert not repo.bare
        origin = repo.remotes.origin
        assert origin.exists()
        val = input('Automatically push to remote master ? (y|n): ')
        if val == "y":
            origin.push('master:master')
            print('Pushed content to remote on master')


if (__name__ == "__main__"):
    # start
    Generator()
