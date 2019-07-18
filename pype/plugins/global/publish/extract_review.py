import os
import pyblish.api
import subprocess
from pype.vendor import clique
from pypeapp import config


class ExtractReview(pyblish.api.InstancePlugin):
    """Extracting Review mov file for Ftrack

    Compulsory attribute of representation is tags list with "review",
    otherwise the representation is ignored.

    All new represetnations are created and encoded by ffmpeg following
    presets found in `pype-config/presets/plugins/global/publish.json:ExtractReview:outputs`. To change the file extension
    filter values use preset's attributes `ext_filter`
    """

    label = "Extract Review"
    order = pyblish.api.ExtractorOrder + 0.02
    families = ["review"]

    def process(self, instance):
        # adding plugin attributes from presets
        publish_presets = config.get_presets()["plugins"]["global"]["publish"]
        plugin_attrs = publish_presets[self.__class__.__name__]
        output_profiles = plugin_attrs.get("outputs", {})

        inst_data = instance.data
        fps = inst_data.get("fps")
        start_frame = inst_data.get("startFrame")

        self.log.debug("Families In: `{}`".format(instance.data["families"]))

        # get representation and loop them
        representations = instance.data["representations"]

        # filter out mov and img sequences
        representations_new = representations.copy()
        for repre in representations:
            if repre['ext'] in plugin_attrs["ext_filter"]:
                tags = repre.get("tags", [])

                self.log.info("Try repre: {}".format(repre))

                if "review" in tags:
                    staging_dir = repre["stagingDir"]
                    for name, profile in output_profiles.items():
                        if any(item in instance.data['families'] for item in profile['families']):
                            if isinstance(repre["files"], list):
                            # if "mov" not in repre['ext']:
                                # get output presets and loop them
                                collections, remainder = clique.assemble(
                                    repre["files"])

                                full_input_path = os.path.join(
                                    staging_dir, collections[0].format(
                                        '{head}{padding}{tail}')
                                )

                                filename = collections[0].format('{head}')
                                if filename.endswith('.'):
                                    filename = filename[:-1]
                            else:
                                self.log.info("1: {}".format(full_input_path))
                                full_input_path = os.path.join(
                                    staging_dir, repre["files"])
                                filename = repre["files"].split(".")[0]

                            mov_file = filename + "_{0}.{1}".format(name, "mov")

                            full_output_path = os.path.join(staging_dir, mov_file)

                            self.log.info("input {}".format(full_input_path))
                            self.log.info("output {}".format(full_output_path))

                            repre_new = repre.copy()

                            self.log.debug("Profile name: {}".format(name))

                            new_tags = tags[:]
                            p_tags = profile.get('tags', [])
                            self.log.info("p_tags: `{}`".format(p_tags))
                            # add families
                            [instance.data["families"].append(t) for t in p_tags
                             if t not in instance.data["families"]]
                            # add to
                            [new_tags.append(t) for t in p_tags
                             if t not in new_tags]

                            self.log.info("new_tags: `{}`".format(new_tags))

                            input_args = []

                            # overrides output file
                            input_args.append("-y")

                            # preset's input data
                            input_args.extend(profile.get('input', []))

                            # necessary input data
                            # adds start arg only if image sequence
                            if "mov" not in repre_new['ext']:
                                input_args.append("-start_number {}".format(
                                    start_frame))

                            input_args.append("-i {}".format(full_input_path))
                            input_args.append("-framerate {}".format(fps))

                            output_args = []
                            # preset's output data
                            output_args.extend(profile.get('output', []))

                            # output filename
                            output_args.append(full_output_path)
                            mov_args = [
                                "ffmpeg",
                                " ".join(input_args),
                                " ".join(output_args)
                            ]
                            subprocess_mov = " ".join(mov_args)

                            # run subprocess
                            sub_proc = subprocess.Popen(subprocess_mov)
                            sub_proc.wait()

                            if not os.path.isfile(full_output_path):
                                self.log.error(
                                    "Quicktime wasn't created succesfully")

                            # create representation data
                            repre_new.update({
                                'name': name,
                                'ext': 'mov',
                                'files': mov_file,
                                "tags": new_tags,
                                "outputName": name
                            })

                            if repre_new.get('preview'):
                                repre_new.pop("preview")
                            if repre_new.get('thumbnail'):
                                repre_new.pop("thumbnail")

                            # adding representation
                            representations_new.append(repre_new)
                else:
                    continue
            else:
                continue


        self.log.debug(
            "new representations: {}".format(representations_new))
        instance.data["representations"] = representations_new

        self.log.debug("Families Out: `{}`".format(instance.data["families"]))
