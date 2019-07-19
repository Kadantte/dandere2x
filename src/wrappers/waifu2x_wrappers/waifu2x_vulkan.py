#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Name: Dandere2X waifu2x-vulkan)
Author: CardinalPanda
Date Created: March 22, 2019
Last Modified: April 2, 2019

Description: # A pretty hacky wrapper for Waifu2x-Vulkan
Behaves pretty similar to waifu2x-caffe, except directory must be
set  (for subprocess call, waifu2x_vulkan_dir_dir keeps this variable) and arguments are slightly different.
Furthermore, waifu2x-vulkan saves files in an annoying way, i.e it becomes image.png.png when saving in batches.
so we need to correct those odd namings.
"""

import logging
import os
import subprocess
import threading

from context import Context
from dandere2x_core.dandere2x_utils import get_lexicon_value
from dandere2x_core.dandere2x_utils import rename_file
from dandere2x_core.dandere2x_utils import wait_on_either_file
from dandere2x_core.dandere2x_utils import file_exists


# this is pretty ugly
class Waifu2xVulkan(threading.Thread):
    def __init__(self, context: Context):
        # load context
        self.frame_count = context.frame_count
        self.waifu2x_vulkan_dir = context.waifu2x_vulkan_dir
        self.waifu2x_vulkan_dir_dir = context.waifu2x_vulkan_dir_dir
        self.differences_dir = context.differences_dir
        self.upscaled_dir = context.upscaled_dir
        self.noise_level = context.noise_level
        self.scale_factor = context.scale_factor
        self.workspace = context.workspace
        self.context = context

        threading.Thread.__init__(self)
        logging.basicConfig(filename=self.workspace + 'waifu2x.log', level=logging.INFO)

    # manually upscale a single file
    @staticmethod
    def upscale_file(context: Context, input_file: str, output_file: str):
        # load context
        waifu2x_vulkan_dir = context.waifu2x_vulkan_dir
        waifu2x_vulkan_dir_dir = context.waifu2x_vulkan_dir_dir
        noise_level = context.noise_level
        scale_factor = context.scale_factor

        waifu2x_vulkan_upscale_frame = context.waifu2x_vulkan_upscale_frame
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[waifu2x_vulkan_dir]", waifu2x_vulkan_dir)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[input_file]", input_file)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[output_file]", output_file)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[scale_factor]", scale_factor)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[noise_level]", noise_level)

        logger = logging.getLogger(__name__)

        exec = waifu2x_vulkan_upscale_frame.split(" ")

        os.chdir(waifu2x_vulkan_dir_dir)

        logger.info("manually upscaling file")
        logger.info(exec)

        subprocess.call(exec, stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)

    # Waifu2x-Converter-Cpp adds this ugly '[NS-L3][x2.000000]' to files, so
    # this function just renames the files so Dandere2x can interpret them correctly.
    def fix_names(self):

        list_of_names = os.listdir(self.upscaled_dir)
        for name in list_of_names:
            if '.png.png' in name:
                rename_file(self.upscaled_dir + name,
                            self.upscaled_dir + name.replace('.png.png', '.png'))

    # This function is tricky. Essentially we do multiple things in one function
    # Because of 'gotchas'

    # First, we make a list of prefixes. Both the desired file name and the produced file name
    # Will start with the same prefix (i.e all the stuff in file_names).

    # Then, we have to specify what the dirty name will end in. in Vulkan's case, it'll have a ".png.png"
    # We then have to do a try / except to try to rename it back to it's clean name, since it may still be
    # being written / used by another program and not safe to edit yet.
    def fix_names_all(self):

        file_names = []
        for x in range(1, self.frame_count):
            file_names.append("output_" + get_lexicon_value(6, x))

        for file in file_names:
            dirty_name = self.upscaled_dir + file + ".png.png"
            clean_name = self.upscaled_dir + file + ".png"

            wait_on_either_file(clean_name, dirty_name)

            if file_exists(clean_name):
                pass

            elif file_exists(dirty_name):
                while file_exists(dirty_name):
                    try:
                        rename_file(dirty_name, clean_name)
                    except PermissionError:
                        pass



    # (description from waifu2x_caffe)
    # The current Dandere2x implementation requires files to be removed from the folder
    # During runtime. As files produced by Dandere2x don't all exist during the initial
    # Waifu2x call, various work arounds are in place to allow Dandere2x and Waifu2x to work in real time.

    # Briefly, 1) Create a list of names that will be upscaled by waifu2x,
    #          2) Call waifu2x to upscale whatever images are in 'differences' folder
    #          3) After waifu2x call is finished, delete whatever files were upscaled, and remove those names from list.
    #             (this is to prevent Waifu2x from re-upscaling the same image again)
    #          4) Repeat this process until all the names are removed.
    def run(self):
        logger = logging.getLogger(__name__)

        waifu2x_vulkan_upscale_frame = self.context.waifu2x_vulkan_upscale_frame
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[waifu2x_vulkan_dir]", self.waifu2x_vulkan_dir)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[input_file]", self.differences_dir)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[output_file]", self.upscaled_dir)
        waifu2x_vulkan_upscale_frame = waifu2x_vulkan_upscale_frame.replace("[scale_factor]", self.scale_factor)

        exec = waifu2x_vulkan_upscale_frame.split(" ")

        # if there are pre-existing files, fix them (this occurs during a resume session)
        self.fix_names()

        # we need to os.chdir to set the directory or else waifu2x-vulkan won't work.
        os.chdir(self.waifu2x_vulkan_dir_dir)

        logger.info("waifu2x_vulkan session")
        logger.info(exec)

        # make a list of names that will eventually (past or future) be upscaled
        names = []
        for x in range(1, self.frame_count):
            names.append("output_" + get_lexicon_value(6, x) + ".png")

        fix_names_forever_thread = threading.Thread(target=self.fix_names_all)
        fix_names_forever_thread.start()

        count_removed = 0

        # remove from the list images that have already been upscaled
        for name in names[::-1]:
            if os.path.isfile(self.upscaled_dir + name):
                names.remove(name)
                count_removed += 1

        if count_removed:
            logger.info("Already have " + str(count_removed) + " upscaled")

        # while there are pictures that have yet to be upscaled, keep calling the upscale command
        while names:

            logger.info("Frames remaining before batch: ")
            logger.info(len(names))
            subprocess.call(exec, stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT) # We're supressing A LOT of errors btw.
            #self.fix_names()

            for name in names[::-1]:
                if os.path.isfile(self.upscaled_dir + name):
                    os.remove(self.differences_dir + name)
                    names.remove(name)
