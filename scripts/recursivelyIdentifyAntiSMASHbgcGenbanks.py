#!/usr/bin/env python

### Program: recursivelyIdentifyAntiSMASHbgcGenbanks.py
### Author: Rauf Salamzade
### Kalan Lab
### UW Madison, Department of Medical Microbiology and Immunology

# BSD 3-Clause License
#
# Copyright (c) 2021, Kalan-Lab
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import argparse
import glob

def create_parser():
	""" Parse arguments """
	parser = argparse.ArgumentParser(description="""
	Program: recursivelyIdentifyAntiSMASHbgcGenbanks.py
	Author: Rauf Salamzade
	Affiliation: Kalan Lab, UW Madison, Department of Medical Microbiology and Immunology

	Program to create AntiSMASH BGC Genbanks listing file needed for lsaBGC-Ready.py. Provided a directory 
	with AntiSMASH results for a set of samples, it will create a two-column, tab-delimited listing file where
	the first column is the sample name and the second is the full path to an individual BGC for the sample. E.g.
	suppose the following setup:
	
	./AntiSMASH-General-Dir/Sample-Name-1/Sample-Name-1_Scaffold-1.region0001.gbk
	./AntiSMASH-General-Dir/Sample-Name-1/Sample-Name-1_Scaffold-5.region0007.gbk
	./AntiSMASH-General-Dir/Sample-Name-2/Sample-Name-1_Scaffold-1.region0002.gbk

	Then it will print to standard output the following:
	
	Sample-Name-1 <tab> /full-path-to/AntiSMASH-General-Dir/Sample-Name-1/Sample-Name-1_Scaffold-1.region0001.gbk
	Sample-Name-1 <tab> /full-path-to/AntiSMASH-General-Dir/Sample-Name-1/Sample-Name-1_Scaffold-5.region0007.gbk
	Sample-Name-2 <tab> /full-path-to/AntiSMASH-General-Dir/Sample-Name-1/Sample-Name-1_Scaffold-1.region0002.gbk

	Note, for files to be considered as BGC Genbanks, they must end with *.gbk and feature ".region" in the file name.
	""", formatter_class=argparse.RawTextHelpFormatter)

	parser.add_argument('-i', '--input_antismash_dir', help='Path to genomic assembly in FASTA format.', required=True)
	parser.add_argument('-f', '--filter_incomplete', help='Filter out incomplete BGCs (those found on contig edges.', required=False, default=False)
	args = parser.parse_args()
	return args


def siftAndPrint():
	"""
	Void function which runs primary workflow for program.
	"""

	"""
	PARSE REQUIRED INPUTS
	"""
	myargs = create_parser()

	input_antismash_dir = os.path.abspath(myargs.input_antismash_dir) + '/'

	try:
		assert(os.path.isdir(input_antismash_dir))
	except:
		raise RuntimeError('Cannot find input directory of antiSMASH results.')

	filter_incomplete_flag = myargs.filter_incomplete

	"""
	START WORKFLOW
	"""

	for full_file_name in glob.glob(input_antismash_dir + "*/*region*.gbk"):
		sample = full_file_name.split('/')[-2]
		contig_edge_flag
		with open(full_file_name) as offn:
			for line in offn:
				line = line.strip()
				if '/contig_edge="True"' in line:
					contig_edge_flag = True

		if not filter_incomplete_flag or (filter_incomplete_flag and contig_edge_flag):
			print(sample + '\t' + full_file_name)

if __name__ == '__main__':
	siftAndPrint()