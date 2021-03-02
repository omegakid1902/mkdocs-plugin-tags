# --------------------------------------------
# Main part of the plugin
#
# JL Diaz (c) 2019
# MIT License
# --------------------------------------------
from collections  import defaultdict
from pathlib import Path
import os
import yaml
import jinja2
from mkdocs.structure.files import File
from mkdocs.structure.nav import Section
from mkdocs.plugins import BasePlugin
from mkdocs.config.config_options import Type


class TagsPlugin(BasePlugin):
    """
    Creates "tags.md" file containing a list of the pages grouped by tags

    It uses the info in the YAML metadata of each page, for the pages which
    provide a "tags" keyword (whose value is a list of strings)
    """

    config_scheme = (
        ('verbose', Type(bool, default=False)),
        ('tags_filename', Type(str, default='tags.md')),
        ('tags_folder', Type(str, default='generated')),
        ('tags_template', Type(str)),
        ('tags_target_folder', Type(str, default='.')),
        ('tags_add_target', Type(bool, default=True)),
        ('tags_create_target', Type(bool, default=True)),
    )

    def __init__(self):
        self.metadata = []
        self.verbose = False
        self.tags_filename = "tags.md"
        self.tags_folder = "generated"
        self.tags_template = None
        self.tags_target_folder = None
        self.tags_add_target = True
        self.tags_create_target = True
        self.tags_dict = {}

    def vprint(self, str):
        if self.verbose:
            print(str)

    def nprint(self, str):
        print(str)

    def on_config(self, config):
        # Re assign the options
        self.verbose = self.config.get("verbose")
        self.tags_filename = Path(self.config.get("tags_filename") or self.tags_filename)
        self.tags_folder = Path(self.config.get("tags_folder") or self.tags_folder)
        self.tags_target_folder = Path(self.config.get("tags_target_folder") or self.tags_target_folder)
        self.tags_add_target = self.config.get("tags_add_target")
        self.tags_create_target = self.config.get("tags_create_target")
        # Make sure that the tags folder is absolute, and exists
        #if not self.tags_folder.is_absolute():
        #    self.tags_folder = Path(config["site_dir"]) / self.tags_folder
        if not self.tags_folder.exists():
            self.tags_folder.mkdir(parents=True)

        if self.config.get("tags_template"):
            self.tags_template = Path(self.config.get("tags_template"))

        if self.tags_add_target and not self.tags_create_target:
            self.nprint("WARNING: meaningless target config (requested to add a target, but not generate it)")

    def on_files(self, files, config):
        # Scan the list of files to extract tags from meta
        for f in files:
            if not f.src_path.endswith(".md"):
                continue
            self.vprint('reading tags from %s' % f.src_path)
            self.metadata.append(get_metadata(f.src_path, config["docs_dir"]))

        self.update_tags_dict(config)

        # Create new file with tags
        if self.tags_create_target:
            self.generate_tags_file()

            # New file to add to the build
            if self.tags_add_target:
                newfile = File(
                    path=str(self.tags_filename),
                    src_dir=str(self.tags_folder),
                    dest_dir=config["site_dir"] / Path(self.tags_target_folder),
                    use_directory_urls=False
                )
                files.append(newfile)

    def on_page_markdown(self, markdown, page, config, files):
        page.meta['all_tags'] = self.tags_dict


    def generate_tags_page(self, data):
        if self.tags_template is None:
            templ_path = Path(__file__).parent  / Path("templates")
            environment = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(templ_path))
                )
            templ = environment.get_template("tags.md.template")
        else:
            environment = jinja2.Environment(
                loader=jinja2.FileSystemLoader(searchpath=str(self.tags_template.parent))
            )
            templ = environment.get_template(str(self.tags_template.name))
        output_text = templ.render(
                tags=sorted(data.items(), key=lambda t: t[0].lower()),
        )
        return output_text

    def update_tags_dict(self, config):
        #sorted_meta = sorted(self.metadata, key=lambda e: e.get("year", 5000) if e else 0)

        num_pages = 0
        pages_with_tags = 0
        self.tags_dict = defaultdict(list)
        for e in self.metadata:
            if not e: continue

            num_pages += 1
            tags = e.get("tags", [])
            if tags is not None and len(tags) > 0:
                pages_with_tags += 1
                for tag in tags:
                    self.tags_dict[tag].append(e)
        
        self.nprint('Tags: Total pages scanned: {0}, pages with tags: {1}, total tags: {2}'.format(num_pages, pages_with_tags, len(self.tags_dict)))
        if self.verbose and len(self.tags_dict) > 0:
            self.vprint('Tags: {0}'.format(self.tags_dict))

    def generate_tags_file(self):
        sorted_meta = sorted(self.metadata, key=lambda e: e.get("year", 5000) if e else 0)
        tag_dict = defaultdict(list)
        for e in sorted_meta:
            if not e:
                continue
            if "title" not in e:
                e["title"] = "Untitled"
            tags = e.get("tags", [])
            if tags is not None:
                for tag in tags:
                    tag_dict[tag].append(e)

        t = self.generate_tags_page(tag_dict)

        with open(str(self.tags_folder / self.tags_filename), "w") as f:
            f.write(t)

# Helper functions

def get_metadata(name, path):
    # Extract metadata from the yaml at the beginning of the file
    def extract_yaml(f):
        result = []
        c = 0
        title = None        
        for line in f:
            sline = line.strip()
            if sline == "---":
                c +=1
                continue
            if c==2:
                if sline:
                    if sline.startswith('# '):
                        title = sline.lstrip('# ')
                    break
            if c==1:
                result.append(line)

        return "".join(result), title

    filename = Path(path) / Path(name)
    with filename.open() as f:
        metadata, title = extract_yaml(f)
        if metadata:
            meta = yaml.load(metadata, Loader=yaml.FullLoader)
            meta.update(filename=name)
            if 'title' not in meta:
                if not title: 
                    title = name.replace('-', ' ').replace('_', ' ')
                    if title.lower() == title: title = title.capitalize()
                meta['title'] = 'Untitled' if title is None else title
            return meta
