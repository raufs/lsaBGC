#!/usr/bin/env python

### Program: lsaBGC-AutoExpansion.py
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
import sys
from time import sleep
import argparse
from lsaBGC.classes.GCF import GCF
from lsaBGC.classes.Pan import Pan
from lsaBGC.classes.BGC import BGC
from lsaBGC import util
import math
from collections import defaultdict
import traceback

lsaBGC_main_directory = '/'.join(os.path.realpath(__file__).split('/')[:-2])
RSCRIPT_FOR_TREESTRUCTURE = lsaBGC_main_directory + '/lsaBGC/Rscripts/createNJTreeAndDefineClades.R'

def create_parser():
	""" Parse arguments """
	parser = argparse.ArgumentParser(description="""
	Program: lsaBGC-Automate.py
	Author: Rauf Salamzade
	Affiliation: Kalan Lab, UW Madison, Department of Medical Microbiology and Immunology

	Program to run lsaBGC-Expansion on each GCF and then consolidate results.

	""", formatter_class=argparse.RawTextHelpFormatter)

	parser.add_argument('-g', '--gcf_listing_dir', help='Directory with GCF listing files.', required=True)
	parser.add_argument('-m', '--orthofinder_matrix', help="OrthoFinder homolog group by sample matrix.", required=True)
	parser.add_argument('-l', '--initial_listing', type=str, help="Tab delimited text file for samples with three columns: (1) sample name (2) Prokka generated Genbank file (*.gbk), and (3) Prokka generated predicted-proteome file (*.faa). Please remove troublesome characters in the sample name.")
	parser.add_argument('-e', '--expansion_listing', help="Path to tab delimited file listing: (1) sample name (2) path to Prokka Genbank and (3) path to Prokka predicted proteome. This file is produced by lsaBGC-AutoProcess.py.", required=True)
	parser.add_argument('-o', '--output_directory', help="Parent output/workspace directory.", required=True)
	parser.add_argument('-c', '--cores', type=int, help="Total number of cores to use.", required=False, default=1)

	args = parser.parse_args()
	return args


def lsaBGC_AutoExpansion():
	"""
	Void function which runs primary workflow for program.
	"""

	"""
	PARSE REQUIRED INPUTS
	"""
	myargs = create_parser()

	outdir = os.path.abspath(myargs.output_directory) + '/'
	gcf_listing_dir = os.path.abspath(myargs.gcf_listing_dir) + '/'
	original_orthofinder_matrix_file = os.path.abspath(myargs.orthofinder_matrix)
	initial_listing_file = os.path.abspath(myargs.initial_listing)
	expansion_listing_file = os.path.abspath(myargs.expansion_listing)

	try:
		assert (os.path.isdir(gcf_listing_dir) and os.path.isfile(original_orthofinder_matrix_file) and os.path.isfile(initial_listing_file) and os.path.isfile(expansion_listing_file))
	except:
		raise RuntimeError('Input directory with GCF listings does not exist, the OrthoFinder sample by homolog matrix file, input file listing initial listings file, expansions listings file, or does not exist. Exiting now ...')

	if os.path.isdir(outdir):
		sys.stderr.write("Output directory exists. Continuing in 5 seconds ...\n ")
		sleep(5)
	else:
		os.system('mkdir %s' % outdir)

	"""
	PARSE OPTIONAL INPUTS
	"""

	cores = myargs.cores

	"""
	START WORKFLOW
	"""

	# create logging object
	log_file = outdir + 'Progress.log'
	logObject = util.createLoggerObject(log_file)

	# Step 0: Log input arguments and update reference and query FASTA files.
	logObject.info("Saving parameters for easier determination of results' provenance in the future.")
	parameters_file = outdir + 'Parameter_Inputs.txt'
	parameter_values = [gcf_listing_dir, initial_listing_file, original_orthofinder_matrix_file,
						expansion_listing_file, outdir, cores]
	parameter_names = ["GCF Listings Directory", "Listing File of Prokka Annotation Files for Initial Set of Samples",
					   "Listing File of Prokka Annotation Files for Expansion/Additional Set of Samples",
					   "OrthoFinder Homolog Matrix", "Output Directory", "Cores"]
	util.logParametersToFile(parameters_file, parameter_names, parameter_values)
	logObject.info("Done saving parameters!")

	exp_outdir = outdir + 'Expansion/'
	if not os.path.isdir(exp_outdir): os.system('mkdir %s' % exp_outdir)

	gcf_expansion_results = defaultdict(dict)
	bgc_lt_evals = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
	bgc_lts = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
	bgc_lt_to_hg = defaultdict(dict)
	original_gcfs = set([])
	for g in os.listdir(gcf_listing_dir):
		gcf_id = g.split('.txt')[0]
		gcf_listing_file = gcf_listing_dir + g
		orthofinder_matrix_file = original_orthofinder_matrix_file
		logObject.info("Beginning expansion for GCF %s" % gcf_id)
		sys.stderr.write("Beginning expansion for GCF %s\n" % gcf_id)

		with open(gcf_listing_file) as oglf:
			for line in oglf:
				line = line.strip()
				sample, bgc_gbk_path = line.split('\t')
				BGC_Object = BGC(bgc_gbk_path, bgc_gbk_path)
				BGC_Object.parseGenbanks(comprehensive_parsing=False)
				curr_bgc_lts = set(BGC_Object.gene_information.keys())
				for lt in curr_bgc_lts:
					bgc_lt_evals[sample][gcf_id][bgc_gbk_path][lt] = -300
					bgc_lts[sample][gcf_id][bgc_gbk_path].add(lt)
				original_gcfs.add(line.split('\t')[1])

		# Run lsaBGC-Expansion.py for GCF
		gcf_exp_outdir = exp_outdir + gcf_id + '/'
		cmd = ['lsaBGC-Expansion.py', '-g', gcf_listing_file, '-m', orthofinder_matrix_file, '-l',
			   initial_listing_file, '-e', expansion_listing_file, '-o', gcf_exp_outdir, '-i', gcf_id,
			   '-c', str(cores)]
		try:
			util.run_cmd(cmd, logObject, stderr=sys.stderr, stdout=sys.stdout)

			updated_gcf_listing_file = gcf_exp_outdir + 'GCF_Expanded.txt'
			gcf_hmm_evalues_file = gcf_exp_outdir + 'GCF_NewInstances_HMMEvalues.txt'

			assert (os.path.isfile(updated_gcf_listing_file))
			assert (os.path.isfile(gcf_hmm_evalues_file))

			gcf_expansion_results[gcf_id] = updated_gcf_listing_file

			with open(gcf_hmm_evalues_file) as oghef:
				for line in oghef:
					line = line.strip()
					bgc_gbk_path, sample, lt, hg, eval = line.split('\t')
					eval = float(eval)
					bgc_lt_evals[sample][gcf_id][bgc_gbk_path][lt] = max(math.log(eval+1e-300, 10), -300)
					bgc_lts[sample][gcf_id][bgc_gbk_path].add(lt)
					bgc_lt_to_hg[bgc_gbk_path][lt] = hg

		except Exception as e:
			logObject.warning("lsaBGC-Expansion.py was unsuccessful, skipping over GCF %s" % gcf_id)
			sys.stderr.write("lsaBGC-Expansion.py was unsuccessful, skipping over GCF %s\n" % gcf_id)
			continue

	updated_gcf_listing_dir = outdir + 'Updated_GCF_Listings/'
	if not os.path.isdir(updated_gcf_listing_dir): os.system('mkdir %s' % updated_gcf_listing_dir)

	# refine and filter overlapping BGCs across GCF expansions
	for sample in bgc_lts:
		for i, gcf1 in enumerate(bgc_lts[sample]):
			for j, gcf2 in enumerate(bgc_lts[sample]):
				if i >= j: continue
				for bgc1 in bgc_lts[sample][gcf1]:
					bgc1_lts = bgc_lts[sample][gcf1][bgc1]
					for bgc2 in bgc_lts[sample][gcf2]:
						bgc2_lts = bgc_lts[sample][gcf2][bgc2]
						if len(bgc1_lts.intersection(bgc2_lts)) > 0 and float(len(bgc1_lts.intersection(bgc2_lts)))/float(len(bgc1_lts)) >= 0.5 and float(len(bgc1_lts.intersection(bgc2_lts)))/float(len(bgc2_lts)) >= 0.5:
							bgc1_score = 0
							bgc2_score = 0
							for lt in bgc1_lts:
								bgc1_score += bgc_lt_evals[sample][gcf1][bgc1][lt]
							for lt in bgc2_lts:
								bgc2_score += bgc_lt_evals[sample][gcf2][bgc2][lt]
							try:
								assert(bgc1_score != bgc2_score)
							except Exception as e:
								logObject.error("Overlapping BGCs exist with equivalent scores for different GCFs. This should not be possible. Exiting now...")
								logObject.error(traceback.format_exc())
								raise RuntimeException("Overlapping BGCs exist with equivalent scores for different GCFs. This should not be possible. Exiting now...")

							gcf_to_edit = None
							bgc_to_remove = None

							if bgc1 in original_gcfs and not bgc2 in original_gcfs:
								gcf_to_edit = gcf2
								bgc_to_remove = bgc2
							elif bgc2 in original_gcfs and not bgc1 in original_gcfs:
								gcf_to_edit = gcf1
								bgc_to_remove = bgc1
							elif bgc1_score < bgc2_score:
								gcf_to_edit = gcf2
								bgc_to_remove = bgc2
							else:
								gcf_to_edit = gcf1
								bgc_to_remove = bgc1

							logObject.info("Overlap found between BGCs %s (%s) and %s (%s), will be removing %s (%s)" % (bgc1, gcf1, bgc2, gcf2, bgc_to_remove, gcf_to_edit))
							gcf_expansion_listing_file = gcf_expansion_results[gcf_to_edit]
							all_lines = []
							with open(gcf_expansion_listing_file) as ogelf:
								for line in ogelf: all_lines.append(line)
							rewrite_handle = open(gcf_expansion_listing_file, 'w')
							for line in all_lines:
								if line.strip().split('\t')[1] != bgc_to_remove:
									rewrite_handle.write(line)
							rewrite_handle.close()

	# create updated general listings file
	updated_listings_file = outdir + 'Sample_Annotation_Files.txt'
	updated_listings_handle = open(updated_listings_file, 'w')
	all_samples = set([])
	with open(initial_listing_file) as oilf:
		for line in oilf:
			all_samples.add(line.strip().split('\t')[0])
			updated_listings_handle.write(line)
	with open(expansion_listing_file) as oelf:
		for line in oelf:
			all_samples.add(line.strip().split('\t')[0])
			updated_listings_handle.write(line)
	updated_listings_handle.close()

	# update OrthoFinder homolog group vs. sample matrix
	sample_hg_lts = defaultdict(lambda: defaultdict(set))
	for gcf in gcf_expansion_results:
		expanded_gcf_listing_file = gcf_expansion_results[gcf]
		final_expanded_gcf_listing_file = updated_gcf_listing_dir + gcf + '.txt'
		final_expanded_gcf_listing_handle = open(final_expanded_gcf_listing_file, 'w')
		with open(expanded_gcf_listing_file) as oeglf:
			for line in oeglf:
				final_expanded_gcf_listing_handle.write(line)
				line = line.strip()
				sample, bgc_gbk_path = line.split('\t')
				if bgc_gbk_path in original_gcfs: continue
				BGC_Object = BGC(bgc_gbk_path, bgc_gbk_path)
				BGC_Object.parseGenbanks(comprehensive_parsing=False)
				curr_bgc_lts = set(BGC_Object.gene_information.keys())
				for lt in curr_bgc_lts:
					if lt in bgc_lt_to_hg[bgc_gbk_path]:
						hg = bgc_lt_to_hg[bgc_gbk_path][lt]
						sample_hg_lts[sample][hg].add(lt)
		final_expanded_gcf_listing_handle.close()

	original_samples = []
	all_hgs = set([])
	with open(orthofinder_matrix_file) as omf:
		for i, line in enumerate(omf):
			line = line.strip('\n')
			ls = line.split('\t')
			if i == 0:
				original_samples = [x.replace(' ', '_').replace('|', '_').replace('"', '_').replace("'", '_').replace("=", "_").replace('-', '_') for x in ls[1:]]
				all_samples = all_samples.union(set(original_samples))
			else:
				hg = ls[0]
				all_hgs.add(hg)
				for j, prot in enumerate(ls[1:]):
					sample_hg_lts[original_samples[j]][hg] = sample_hg_lts[original_samples[j]][hg].union(set(prot.split(', ')))

	expanded_orthofinder_matrix_file = outdir + 'Orthogroups.expanded.csv'
	expanded_orthofinder_matrix_handle = open(expanded_orthofinder_matrix_file, 'w')

	header = [''] + [s for s in sorted(all_samples)]
	expanded_orthofinder_matrix_handle.write('\t'.join(header) + '\n')
	for hg in sorted(all_hgs):
		printlist = [hg]
		for s in sorted(all_samples):
			printlist.append(', '.join(sample_hg_lts[s][hg]))
		expanded_orthofinder_matrix_handle.write('\t'.join(printlist) + '\n')
	expanded_orthofinder_matrix_handle.close()

	# Close logging object and exit
	util.closeLoggerObject(logObject)
	sys.exit(0)

if __name__ == '__main__':
	lsaBGC_AutoExpansion()
