import os
import sys
import logging
import traceback
import statistics
import random
import subprocess
import multiprocessing
from scipy.stats import f_oneway
from ete3 import Tree
from Bio import SeqIO
from Bio.Seq import Seq
from operator import itemgetter
from collections import defaultdict
from lsaBGC.classes.Pan import Pan
from lsaBGC import util

lsaBGC_main_directory = '/'.join(os.path.realpath(__file__).split('/')[:-3])
RSCRIPT_FOR_BGSEE = lsaBGC_main_directory + '/lsaBGC/Rscripts/bgSee.R'
RSCRIPT_FOR_CLUSTER_ASSESSMENT_PLOTTING = lsaBGC_main_directory + '/lsaBGC/Rscripts/generatePopGenePlots.R'
RSCRIPT_FOR_TAJIMA = lsaBGC_main_directory + '/lsaBGC/Rscripts/calculateTajimasD.R'

class GCF(Pan):
	def __init__(self, bgc_genbanks_listing, gcf_id='GCF_X', logObject=None, lineage_name='Unnamed lineage'):
		super().__init__(bgc_genbanks_listing, lineage_name=lineage_name, logObject=logObject)
		self.gcf_id = gcf_id

		#######
		## Variables not set during initialization
		#######

		# General variables
		self.hg_to_color = None
		self.hg_order_scores = defaultdict(int)
		self.scc_homologs = set([])

		# Sequence and alignment directories
		self.nucl_seq_dir = None
		self.prot_seq_dir = None
		self.prot_alg_dir = None
		self.codo_alg_dir = None

		# Concatenated HMMER3 HMM profiles database of homolog groups in GCF
		self.concatenated_profile_HMM = None

	def modifyPhylogenyForSamplesWithMultipleBGCs(self, input_phylogeny, result_phylogeny):
		"""
		Function which takes in an input phylogeny and produces a replicate resulting phylogeny with samples/leafs which
		have multiple BGC instances for a GCF expanded.

		:param input_phylogeny: input newick phylogeny file
		:result result_phylogeny: resulting newick phylogeny file
		"""
		try:
			number_of_added_leaves = 0
			t = Tree(input_phylogeny)
			for node in t.traverse('postorder'):
				if node.name in self.sample_bgcs and len(self.sample_bgcs[node.name]) > 1:
					og_node_name = node.name
					node.name = node.name + '_INNERNODE'
					for bgc_id in self.sample_bgcs[og_node_name]:
						# if bgc_id == node.name: continue
						node.add_child(name=bgc_id)
						child_node = t.search_nodes(name=bgc_id)[0]
						child_node.dist = 0
						if bgc_id != og_node_name: number_of_added_leaves += 1
			t.write(format=1, outfile=result_phylogeny)
			if self.logObject:
				self.logObject.info(
					"New phylogeny with an additional %d leafs to reflect samples with multiple BGCs can be found at: %s." % (
						number_of_added_leaves, result_phylogeny))
		except Exception as e:
			if self.logObject:
				self.logObject.error(
					"Had difficulties properly editing phylogeny to duplicate leafs for samples with multiple BGCs for GCF.")
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

	def assignColorsToHGs(self, gene_to_hg, bgc_genes):
		"""
		Simple function to associate each homolog group with a color for consistent coloring.

		:param gene_to_hg: gene to HG relationship.
		:param bgc_genes:  set of genes per HG.
		:return: dictionary mapping each HG to a hex color value.
		"""

		hg_bgc_counts = defaultdict(int)
		for b in bgc_genes:
			for g in bgc_genes[b]:
				if g in gene_to_hg:
					hg_bgc_counts[gene_to_hg[g]] += 1

		hgs = set([])
		for c in hg_bgc_counts:
			if hg_bgc_counts[c] > 1:
				hgs.add(c)

		# read in list of colors
		dir_path = '/'.join(os.path.dirname(os.path.realpath(__file__)).split('/')[:-1]) + '/'
		colors_file = dir_path + 'colors_200.txt'
		colors = []
		with open(colors_file) as ocf:
			colors = [x.strip() for x in ocf.readlines()]
		random.shuffle(colors)

		hg_to_color = {}
		for i, c in enumerate(set(hgs)):
			hg_to_color[c] = colors[i]
		self.hg_to_color = hg_to_color

	def createItolBGCSeeTrack(self, result_track_file):
		"""
		Function to create a track file for visualizing BGC gene architecture across a phylogeny in the interactive tree
		of life (iTol)

		:param result_track_file: The path to the resulting iTol track file for BGC gene visualization.
		"""
		try:
			track_handle = open(result_track_file, 'w')

			if self.logObject:
				self.logObject.info("Writing iTol track file to: %s" % result_track_file)
				self.logObject.info("Track will have label: %s" % self.gcf_id)

			# write header for iTol track file
			track_handle.write('DATASET_DOMAINS\n')
			track_handle.write('SEPARATOR TAB\n')
			track_handle.write('DATASET_LABEL\t%s\n' % self.gcf_id)
			track_handle.write('COLOR\t#000000\n')
			track_handle.write('BORDER_WIDTH\t1\n')
			track_handle.write('BORDER_COLOR\t#000000\n')
			track_handle.write('SHOW_DOMAIN_LABELS\t0\n')
			track_handle.write('DATA\n')

			# write the rest of the iTol track file for illustrating genes across BGC instances
			ref_hg_directions = {}
			bgc_gene_counts = defaultdict(int)
			for bgc in self.bgc_genes:
				bgc_gene_counts[bgc] = len(self.bgc_genes[bgc])

			for i, item in enumerate(sorted(bgc_gene_counts.items(), key=itemgetter(1), reverse=True)):
				bgc = item[0]
				curr_bgc_genes = self.bgc_genes[bgc]
				last_gene_end = max([self.comp_gene_info[lt]['end'] for lt in curr_bgc_genes])
				printlist = [bgc, str(last_gene_end)]
				hg_directions = {}
				hg_lengths = defaultdict(list)
				for lt in curr_bgc_genes:
					ginfo = self.comp_gene_info[lt]
					hg = 'singleton'
					if lt in self.gene_to_hg:
						hg = self.gene_to_hg[lt]
					shape = 'None'
					if ginfo['direction'] == '+':
						shape = 'TR'
					elif ginfo['direction'] == '-':
						shape = 'TL'
					gstart = ginfo['start']
					gend = ginfo['end']
					hg_color = "#dbdbdb"
					if hg in self.hg_to_color:
						hg_color = self.hg_to_color[hg]
					gene_string = '|'.join([str(x) for x in [shape, gstart, gend, hg_color, hg]])
					printlist.append(gene_string)
					if hg != 'singleton':
						hg_directions[hg] = ginfo['direction']
						hg_lengths[hg].append(gend - gstart)
				if i == 0:
					ref_hg_directions = hg_directions
					track_handle.write('\t'.join(printlist) + '\n')
				else:
					flip_support = 0
					keep_support = 0
					for c in ref_hg_directions:
						if not c in hg_directions: continue
						hg_weight = statistics.mean(hg_lengths[c])
						if hg_directions[c] == ref_hg_directions[c]:
							keep_support += hg_weight
						else:
							flip_support += hg_weight

					# flip the genbank visual if necessary, first BGC processed is used as reference guide
					if flip_support > keep_support:
						flip_printlist = printlist[:2]
						for gene_string in printlist[2:]:
							gene_info = gene_string.split('|')
							new_shape = None
							if gene_info[0] == 'TR':
								new_shape = 'TL'
							elif gene_info[0] == 'TL':
								new_shape = 'TR'
							new_gstart = int(last_gene_end) - int(gene_info[2])
							new_gend = int(last_gene_end) - int(gene_info[1])
							new_gene_info = '|'.join([new_shape, str(new_gstart), str(new_gend)] + gene_info[-2:])
							flip_printlist.append(new_gene_info)
						track_handle.write('\t'.join(flip_printlist) + '\n')
					else:
						track_handle.write('\t'.join(printlist) + '\n')
			track_handle.close()
		except Exception as e:
			if self.logObject:
				self.logObject.error("Had difficulties creating iTol track for visualization of BGC gene architecture.")
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

	def visualizeGCFViaR(self, gggenes_track_file, heatmap_track_file, phylogeny_file, result_pdf_file):
		"""
		Function to create tracks for visualization of gene architecture of BGCs belonging to GCF and run Rscript bgSee.R
		to produce automatic PDFs of plots. In addition, bgSee.R also produces a heatmap to more easily identify homolog
		groups which are conserved across isolates found to feature GCF.

		:param gggenes_track_file: Path to file with gggenes track information (will be created/written to by function, if it doesn't exist!)
		:param heatmap_track_file: Path to file for heatmap visual component (will be created/written to by function, if it doesn't exist!)
		:param phylogeny_file: Phylogeny to use for visualization.
		:param result_pdf_file: Path to PDF file where plots from bgSee.R will be written to.
		"""
		try:
			if os.path.isfile(gggenes_track_file) or os.path.isfile(heatmap_track_file):
				os.system('rm -f %s %s' % (gggenes_track_file, heatmap_track_file))
			gggenes_track_handle = open(gggenes_track_file, 'w')
			heatmap_track_handle = open(heatmap_track_file, 'w')
			if self.logObject:
				self.logObject.info("Writing gggenes input file to: %s" % gggenes_track_file)
				self.logObject.info("Writing heatmap input file to: %s" % heatmap_track_file)
			# write header for track files
			gggenes_track_handle.write('label\tgene\tstart\tend\tforward\tog\tog_color\n')
			heatmap_track_handle.write('label\tog\tog_presence\tog_count\n')

			ref_hg_directions = {}

			bgc_gene_counts = defaultdict(int)
			for bgc in self.bgc_genes:
				bgc_gene_counts[bgc] = len(self.bgc_genes[bgc])

			tree_obj = Tree(phylogeny_file)
			bgc_weights = defaultdict(int)
			for leaf in tree_obj:
				bgc_weights[str(leaf).strip('\n').lstrip('-')] += 1

			bgc_hg_presence = defaultdict(lambda: defaultdict(lambda: 'Absent'))
			hg_counts = defaultdict(int)
			for i, item in enumerate(sorted(bgc_gene_counts.items(), key=itemgetter(1), reverse=True)):
				bgc = item[0]
				curr_bgc_genes = self.bgc_genes[bgc]
				last_gene_end = max([self.comp_gene_info[lt]['end'] for lt in curr_bgc_genes])
				printlist = []
				hg_directions = {}
				hg_lengths = defaultdict(list)
				for lt in curr_bgc_genes:
					ginfo = self.comp_gene_info[lt]
					hg = 'singleton'
					if lt in self.gene_to_hg:
						hg = self.gene_to_hg[lt]

					gstart = ginfo['start']
					gend = ginfo['end']
					forward = "FALSE"
					if ginfo['direction'] == '+': forward = "TRUE"

					hg_color = '"#dbdbdb"'
					if hg in self.hg_to_color:
						hg_color = '"' + self.hg_to_color[hg] + '"'

					gene_string = '\t'.join([str(x) for x in [bgc, lt, gstart, gend, forward, hg, hg_color]])
					printlist.append(gene_string)
					if hg != 'singleton':
						bgc_hg_presence[bgc][hg] = hg
						hg_counts[hg] += bgc_weights[bgc]
						hg_directions[hg] = ginfo['direction']
						hg_lengths[hg].append(gend - gstart)
				if i == 0:
					ref_hg_directions = hg_directions
					gggenes_track_handle.write('\n'.join(printlist) + '\n')
				else:
					flip_support = 0
					keep_support = 0
					for c in ref_hg_directions:
						if not c in hg_directions: continue
						hg_weight = statistics.mean(hg_lengths[c])
						if hg_directions[c] == ref_hg_directions[c]:
							keep_support += hg_weight
						else:
							flip_support += hg_weight

					# flip the genbank visual if necessary, first BGC processed is used as reference guide
					if flip_support > keep_support:
						flip_printlist = []
						for gene_string in printlist:
							gene_info = gene_string.split('\t')
							new_forward = 'TRUE'
							if gene_info[4] == 'TRUE': new_forward = 'FALSE'
							new_gstart = int(last_gene_end) - int(gene_info[3])
							new_gend = int(last_gene_end) - int(gene_info[2])
							new_gene_string = '\t'.join([str(x) for x in
														 [gene_info[0], gene_info[1], new_gstart, new_gend, new_forward,
															gene_info[-2], gene_info[-1]]])
							flip_printlist.append(new_gene_string)
						gggenes_track_handle.write('\n'.join(flip_printlist) + '\n')
					else:
						gggenes_track_handle.write('\n'.join(printlist) + '\n')
			gggenes_track_handle.close()

			for bgc in bgc_hg_presence:
				for hg in hg_counts:
					heatmap_track_handle.write(
						'\t'.join([bgc, hg, bgc_hg_presence[bgc][hg], str(hg_counts[hg])]) + '\n')
			heatmap_track_handle.close()
		except Exception as e:
			if self.logObject:
				self.logObject.error(
					"Had difficulties creating tracks for visualization of BGC gene architecture along phylogeny using R libraries.")
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

		rscript_plot_cmd = ["Rscript", RSCRIPT_FOR_BGSEE, phylogeny_file, gggenes_track_file, heatmap_track_file,
							result_pdf_file]
		if self.logObject:
			self.logObject.info('Running R-based plotting with the following command: %s' % ' '.join(rscript_plot_cmd))
		try:
			subprocess.call(' '.join(rscript_plot_cmd), shell=True, stdout=subprocess.DEVNULL,
							stderr=subprocess.DEVNULL,
							executable='/bin/bash')
			self.logObject.info('Successfully ran: %s' % ' '.join(rscript_plot_cmd))
		except Exception as e:
			if self.logObject:
				self.logObject.error('Had an issue running: %s' % ' '.join(rscript_plot_cmd))
				self.logObject.error(traceback.format_exc())
			raise RuntimeError('Had an issue running: %s' % ' '.join(rscript_plot_cmd))

		if self.logObject:
			self.logObject.info('Plotting completed (I think successfully)!')

	def constructCodonAlignments(self, outdir, cores=1, only_scc=False):
		"""
		Function to automate construction of codon alignments. This function first extracts protein and nucleotide sequnces
		from BGC Genbanks, then creates protein alignments for each homolog group using MAFFT, and finally converts those
		into codon alignments using PAL2NAL.

		:param outdir: Path to output/workspace directory. Intermediate files (like extracted nucleotide and protein
					   sequences, protein and codon alignments, will be writen to respective subdirectories underneath this
					   one).
		:param cores: Number of cores/threads to use when fake-parallelizing jobs using multiprocessing.
		:param only_scc: Whether to construct codon alignments only for homolog groups which are found to be core and in
						 single copy for samples with the GCF. Note, if working with draft genomes and the BGC is fragmented
						 this should be able to still identify SCC homolog groups across the BGC instances belonging to the
						 GCF.
		"""

		nucl_seq_dir = os.path.abspath(outdir + 'Nucleotide_Sequences') + '/'
		prot_seq_dir = os.path.abspath(outdir + 'Protein_Sequences') + '/'
		prot_alg_dir = os.path.abspath(outdir + 'Protein_Alignments') + '/'
		codo_alg_dir = os.path.abspath(outdir + 'Codon_Alignments') + '/'

		if not os.path.isdir(nucl_seq_dir): os.system('mkdir %s' % nucl_seq_dir)
		if not os.path.isdir(prot_seq_dir): os.system('mkdir %s' % prot_seq_dir)
		if not os.path.isdir(prot_alg_dir): os.system('mkdir %s' % prot_alg_dir)
		if not os.path.isdir(codo_alg_dir): os.system('mkdir %s' % codo_alg_dir)

		all_samples = set(self.bgc_sample.values())
		try:
			inputs = []
			for hg in self.hg_genes:
				# if len(self.hg_genes[hg]) < 2: continue
				sample_counts = defaultdict(int)
				gene_sequences = {}
				for gene in self.hg_genes[hg]:
					gene_info = self.comp_gene_info[gene]
					bgc_id = gene_info['bgc_name']
					sample_id = self.bgc_sample[bgc_id]
					nucl_seq = gene_info['nucl_seq']
					prot_seq = gene_info['prot_seq']
					sample_counts[sample_id] += 1
					gid = sample_id + '|' + gene
					if only_scc:
						gid = sample_id
					gene_sequences[gid] = tuple([nucl_seq, prot_seq])
				samples_with_single_copy = set([s[0] for s in sample_counts.items() if s[1] == 1])
				# check that cog is single-copy-core
				if only_scc and len(samples_with_single_copy.symmetric_difference(all_samples)) > 0:
					continue
				elif only_scc and self.logObject:
					self.logObject.info('Homolog group %s detected as SCC across samples (not individual BGCs).' % hg)
				inputs.append(
					[hg, gene_sequences, nucl_seq_dir, prot_seq_dir, prot_alg_dir, codo_alg_dir, self.logObject])

			p = multiprocessing.Pool(cores)
			p.map(create_codon_msas, inputs)

			self.nucl_seq_dir = nucl_seq_dir
			self.prot_seq_dir = prot_seq_dir
			self.prot_alg_dir = prot_alg_dir
			self.codo_alg_dir = codo_alg_dir

		except Exception as e:
			if self.logObject:
				self.logObject.error("Issues with create protein/codon alignments of SCC homologs for BGC.")
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

	def constructGCFPhylogeny(self, output_alignment, output_phylogeny):
		"""
		Function to create phylogeny based on codon alignments of SCC homolog groups for GCF.

		:param output_alignment: Path to output file for concatenated SCC homolog group alignment.
		:param output_phylogeny: Path to output file for approximate maximum-likelihood phylogeny produced by FastTree2 from
							     concatenated SCC homolog group alignment.
		"""
		try:
			bgc_sccs = defaultdict(lambda: "")
			fasta_data = []
			fasta_data_tr = []

			for f in os.listdir(self.codo_alg_dir):
				cog_align_msa = self.codo_alg_dir + f
				# concatenate gene alignments
				with open(cog_align_msa) as opm:
					for rec in SeqIO.parse(opm, 'fasta'):
						bgc_sccs['>' + rec.id] += str(rec.seq).upper()

			for b in bgc_sccs:
				fasta_data.append([b] + list(bgc_sccs[b]))

			for i, ls in enumerate(zip(*fasta_data)):
				if i == 0:
					fasta_data_tr.append(ls)
				else:
					n_count = len([x for x in ls if x == '-'])
					if (float(n_count) / len(ls)) < 0.1:
						fasta_data_tr.append(list(ls))

			scc_handle = open(output_alignment, 'w')

			for rec in zip(*fasta_data_tr):
				scc_handle.write(rec[0] + '\n' + ''.join(rec[1:]) + '\n')
			scc_handle.close()
		except Exception as e:
			if self.logObject:
				self.logObject.error('Had issues with creating concatenated alignment of the SCC homolog groups.')
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

		# use FastTree2 to construct phylogeny
		fasttree_cmd = ['fasttree', '-nt', output_alignment, '>', output_phylogeny]
		if self.logObject:
			self.logObject.info('Running FastTree2 with the following command: %s' % ' '.join(fasttree_cmd))
		try:
			subprocess.call(' '.join(fasttree_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
							executable='/bin/bash')
			if self.logObject:
				self.logObject.info('Successfully ran: %s' % ' '.join(fasttree_cmd))
		except Exception as e:
			if self.logObject:
				self.logObject.error('Had an issue running: %s' % ' '.join(fasttree_cmd))
				self.logObject.error(traceback.format_exc())
			raise RuntimeError('Had an issue running: %s' % ' '.join(fasttree_cmd))

	def refineBGCGenbanks(self, new_gcf_listing_file, outdir, first_boundary_homolog, second_boundary_homolog):
		"""
		Function to refine BGC Genbanks based on boundaries defined by two single copy core homolog groups. Genbanks
		are filtered to retain only features in between the positions of the two boundary homolog groups. Coordinates
		relevant to the BGC framework are updated (but not all location coordinates!!!).

		:param new_gcf_listing_file: Path to where new GCF listing file will be written.
		:param outdir: Path to workspace directory.
		:param first_boundary_homolog: Identifier of the first boundary homolog group
		:param second_boundary_homolog: Identifier of the second boundary homolog group
		"""
		try:
			refined_gbks_dir = outdir + 'Refined_Genbanks/'
			if not os.path.isdir(refined_gbks_dir): os.system('mkdir %s' % refined_gbks_dir)

			nglf_handle = open(new_gcf_listing_file, 'w')

			first_boundary_homolog_genes = self.hg_genes[first_boundary_homolog]
			second_boundary_homolog_genes = self.hg_genes[second_boundary_homolog]

			for bgc in self.pan_bgcs:
				bgc_genes = set(self.pan_bgcs[bgc].gene_information.keys())
				bgc_fbh_genes = bgc_genes.intersection(first_boundary_homolog_genes)
				bgc_sbh_genes = bgc_genes.intersection(second_boundary_homolog_genes)
				if len(bgc_fbh_genes) == 1 and len(bgc_sbh_genes) == 1:
					refined_gbk = refined_gbks_dir + self.bgc_gbk[bgc].split('/')[-1]
					self.pan_bgcs[bgc].refineGenbank(refined_gbk, list(bgc_fbh_genes)[0], list(bgc_sbh_genes)[0])
					nglf_handle.write('%s\t%s\n' % (self.bgc_sample[bgc], refined_gbk))
				elif self.logObject:
					self.logObject.warning(
						"Dropping the BGC genbank %s from consideration / refinement process because it does not have the boundary homolog groups in single-copy copy." %
						self.bgc_gbk[bgc])
			nglf_handle.close()

		except:
			if self.logObject:
				self.logObject.error('Had an issue refining BGC genbanks associated with GCF')
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

	def determineCogOrderIndex(self):
		"""
		Function to determine an "ordering" score for homolog groups in GCF. The order score is relative to each GCF,
		even a homolog group has a large or small order score indicates it is on the edges (beginning will be chosen
		arbitrarily).
		"""
		try:
			ref_hg_directions = {}
			bgc_gene_counts = defaultdict(int)
			for bgc in self.bgc_genes:
					bgc_gene_counts[bgc] = len(self.bgc_genes[bgc])

			for i, item in enumerate(sorted(bgc_gene_counts.items(), key=itemgetter(1), reverse=True)):
				bgc = item[0]
				curr_bgc_genes = self.bgc_genes[bgc]
				hg_directions = {}
				hg_lengths = defaultdict(list)
				hg_starts = {}
				for g in curr_bgc_genes:
					ginfo = self.comp_gene_info[g]
					gstart = ginfo['start']
					gend = ginfo['end']
					if g in self.gene_to_hg:
						hg = self.gene_to_hg[g]
						hg_directions[hg] = ginfo['direction']
						hg_lengths[hg].append(gend - gstart)
						hg_starts[hg] = ginfo['start']

				reverse_flag = False
				if i == 0:
					ref_hg_directions = hg_directions
				else:
					flip_support = 0
					keep_support = 0
					for c in ref_hg_directions:
						if not c in hg_directions: continue
						cog_weight = statistics.mean(hg_lengths[c])
						if hg_directions[c] == ref_hg_directions[c]:
							keep_support += cog_weight
						else:
							flip_support += cog_weight

					# reverse ordering
					if flip_support > keep_support:
						reverse_flag = True
				for c in sorted(hg_starts.items(), key=itemgetter(1), reverse=reverse_flag):
						self.hg_order_scores[c[0]] += c[1]

		except Exception as e:
			if self.logObject:
				self.logObject.error("Issues in attempting to calculate order score for each homolog group.")
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

	def runPopulationGeneticsAnalysis(self, outdir, cores=1):
		"""
		Wrapper function which serves to parallelize population genetics analysis.

		:param outdir: The path to the workspace / output directory.
		:param cores: The number of cores (will be used for parallelizing)
		"""

		popgen_dir = outdir + 'Codon_PopGen_Analyses/'
		plots_dir = outdir + 'Codon_MSA_Plots/'
		if not os.path.isdir(popgen_dir): os.system('mkdir %s' % popgen_dir)
		if not os.path.isdir(plots_dir): os.system('mkdir %s' % plots_dir)

		final_output_handle = open(outdir + 'Ortholog_Group_Information.txt', 'w')
		header = ['cog', 'annotation', 'cog_order_index', 'cog_median_copy_count', 'median_gene_length',
				  'is_core_to_bgc', 'bgcs_with_cog', 'proportion_of_samples_with_cog', 'Tajimas_D', 'core_codons',
				  'total_variable_codons', 'nonsynonymous_codons', 'synonymous_codons', 'dn_ds', 'all_domains']
		if self.bgc_population != None:
			header += ['populations_with_cog', 'population_proportion_of_members_with_cog', 'one_way_ANOVA_pvalues']

		final_output_handle.write('\t'.join(header) + '\n')

		inputs = []
		for f in os.listdir(self.codo_alg_dir):
			hg = f.split('.msa.fna')[0]
			codon_alignment_fasta = self.codo_alg_dir + f
			inputs.append([hg, codon_alignment_fasta, popgen_dir, plots_dir, self.comp_gene_info, self.hg_genes,
						   self.bgc_sample, self.hg_prop_multi_copy, self.hg_order_scores, self.sample_population,
						   self.logObject])

		p = multiprocessing.Pool(cores)
		p.map(popgen_analysis_of_hg, inputs)

		for f in os.listdir(popgen_dir):
			if not f.endswith('_stats.txt'): continue
			with open(popgen_dir + f) as opf:
				for line in opf:
					line = line
					final_output_handle.write(line)
		final_output_handle.close()

	def constructHMMProfiles(self, outdir, cores=1):
		"""
		Wrapper function to construct Hmmer3 HMMs for each of the homolog groups.

		:param outdir: The path to the workspace / output directory.
		:param cores: The number of cores (will be used for parallelizing)
		"""

		prot_seq_dir = os.path.abspath(outdir + 'Protein_Sequences') + '/'
		prot_alg_dir = os.path.abspath(outdir + 'Protein_Alignments') + '/'
		prot_hmm_dir = os.path.abspath(outdir + 'Profile_HMMs') + '/'
		if not os.path.isdir(prot_seq_dir): os.system('mkdir %s' % prot_seq_dir)
		if not os.path.isdir(prot_alg_dir): os.system('mkdir %s' % prot_alg_dir)
		if not os.path.isdir(prot_hmm_dir): os.system('mkdir %s' % prot_hmm_dir)

		all_samples = set(self.bgc_sample.values())
		try:
			inputs = []
			for hg in self.hg_genes:
				sample_counts = defaultdict(int)
				sample_sequences = {}
				for gene in self.hg_genes[hg]:
					gene_info = self.comp_gene_info[gene]
					bgc_id = gene_info['bgc_name']
					sample_id = self.bgc_sample[bgc_id]
					prot_seq = gene_info['prot_seq']
					sample_counts[sample_id] += 1
					sample_sequences[sample_id] = prot_seq
				samples_with_single_copy = set([s[0] for s in sample_counts.items() if s[1] == 1])
				# check that cog is single-copy-core
				if len(samples_with_single_copy.symmetric_difference(all_samples)) == 0: self.scc_homologs.add(hg)
				if self.logObject:
					self.logObject.info('Homolog group %s detected as SCC across samples (not individual BGCs).' % hg)
				inputs.append([hg, sample_sequences, prot_seq_dir, prot_alg_dir, prot_hmm_dir, self.logObject])

			p = multiprocessing.Pool(cores)
			p.map(create_hmm_profiles, inputs)

			if self.logObject:
				self.logObject.info(
					"Successfully created profile HMMs for each homolog group. Now beginning concatenation into single file.")
			self.concatenated_profile_HMM = outdir + 'All_GCF_Homologs.hmm'
			os.system('rm -f %s' % self.concatenated_profile_HMM)
			for f in os.listdir(prot_hmm_dir):
				os.system('cat %s >> %s' % (prot_hmm_dir + f, self.concatenated_profile_HMM))

			hmmpress_cmd = ['hmmpress', self.concatenated_profile_HMM]
			if self.logObject:
				self.logObject.info(
				'Running hmmpress on concatenated profiles with the following command: %s' % ' '.join(hmmpress_cmd))
			try:
				subprocess.call(' '.join(hmmpress_cmd), shell=True, stdout=subprocess.DEVNULL,
								stderr=subprocess.DEVNULL,
								executable='/bin/bash')
				if self.logObject:
					self.logObject.info('Successfully ran: %s' % ' '.join(hmmpress_cmd))
			except:
				if self.logObject:
					self.logObject.error('Had an issue running: %s' % ' '.join(hmmpress_cmd))
					self.logObject.error(traceback.format_exc())
				raise RuntimeError('Had an issue running: %s' % ' '.join(hmmpress_cmd))
			self.concatenated_profile_HMM

		except:
			if self.logObject:
				self.logObject.error("Issues with running hmmpress on profile HMMs.")
				self.logObject.error(traceback.format_exc())
			raise RuntimeError(traceback.format_exc())

	def runHMMScanAndAssignBGCsToGCF(self, outdir, prokka_genbanks_dir, prokka_proteomes_dir, orthofinder_matrix_file, cores=1):
		"""

		"""
		search_res_dir = os.path.abspath(outdir + 'HMMScan_Results') + '/'
		if not os.path.isdir(search_res_dir): os.system('mkdir %s' % search_res_dir)

		tot_bgc_proteins = defaultdict(int)
		hmmscan_cmds = []
		for i, cb_tuple in enumerate(comprehensive_bgcs):
			sample, bgc_genbank, bgc_proteome = cb_tuple
			with open(bgc_proteome) as obp:
				for rec in SeqIO.parse(obp, 'fasta'):
					tot_bgc_proteins[bgc_genbank] += 1
			result_file = search_res_dir + str(i) + '.txt'
			hmmscan_cmd = ['hmmscan', '--max', '--cpu', '1', '--tblout', result_file, concat_hmm_profiles, bgc_proteome,
						   logObject]
			hmmscan_cmds.append(hmmscan_cmd)

		p = multiprocessing.Pool(cores)
		p.map(util.multiProcess, hmmscan_cmds)
		p.close()

		protein_hits = defaultdict(list)
		sample_cogs = defaultdict(set)
		bgc_cogs = defaultdict(set)
		sample_bgcs = defaultdict(set)
		sample_cog_proteins = defaultdict(lambda: defaultdict(set))
		for i, cb_tuple in enumerate(comprehensive_bgcs):
			sample, bgc_genbank, bgc_proteome = cb_tuple
			sample_bgcs[sample].add(bgc_genbank)
			result_file = search_res_dir + str(i) + '.txt'
			assert (os.path.isfile(result_file))
			with open(result_file) as orf:
				for line in orf:
					if line.startswith("#"): continue
					line = line.strip()
					ls = line.split()
					cog = ls[0]
					samp, bgc, protein_id = ls[2].split('|')
					eval = float(ls[4])
					if eval <= 1e-5:
						protein_hits[protein_id].append([cog, eval, sample, bgc_genbank])

		for p in protein_hits:
			for i, hits in enumerate(sorted(protein_hits[p], key=itemgetter(1))):
				if i == 0:
					sample_cogs[hits[2]].add(hits[0])
					bgc_cogs[hits[3]].add(hits[0])
					sample_cog_proteins[hits[2]][hits[0]].add(p)

		expanded_orthofinder_matrix_file = outdir + 'Orthogroups.expanded.csv'
		expanded_gcf_list_file = outdir + 'GCF_Expanded.txt'

		expanded_orthofinder_matrix_handle = open(expanded_orthofinder_matrix_file, 'w')
		expanded_gcf_list_handle = open(expanded_gcf_list_file, 'w')

		valid_bgcs = set([])
		for sample in sample_cogs:
			if len(scc_homologs.difference(sample_cogs[sample])) == 0:
				for bgc_gbk in sample_bgcs[sample]:
					if float(len(bgc_cogs[bgc_gbk])) / tot_bgc_proteins[bgc_gbk] >= 0.5 and len(
							bgc_cogs[bgc_gbk]) >= 3 and len(scc_homologs.intersection(bgc_cogs[bgc_gbk])) >= 1:
						valid_bgcs.add(bgc_gbk)

		bgc_cogs = defaultdict(set)
		sample_cog_proteins = defaultdict(lambda: defaultdict(set))
		for p in protein_hits:
			for i, hits in enumerate(sorted(protein_hits[p], key=itemgetter(1))):
				if i != 0 or not hits[3] in valid_bgcs: continue
				bgc_cogs[hits[3]].add(hits[0])
				sample_cog_proteins[hits[2]][hits[0]].add(p)

		all_samples = set([])
		for sample in sample_cogs:
			scc_check = True
			for cog in scc_homologs:
				if len(sample_cog_proteins[sample][cog]) != 1: scc_check = False
			if not scc_check: continue
			for bgc_gbk in sample_bgcs[sample]:
				if float(len(bgc_cogs[bgc_gbk])) / tot_bgc_proteins[bgc_gbk] >= 0.5 and len(
						bgc_cogs[bgc_gbk]) >= 3 and len(
						scc_homologs.intersection(bgc_cogs[bgc_gbk])) >= 1:
					expanded_gcf_list_handle.write('\t'.join([sample, bgc_gbk]) + '\n')
					all_samples.add(sample)

		original_samples = []
		all_cogs = set([])
		with open(orthofinder_matrix_file) as omf:
			for i, line in enumerate(omf):
				line = line.strip('\n')
				ls = line.split('\t')
				if i == 0:
					original_samples = ls[1:]
					all_samples = all_samples.union(set(original_samples))
				else:
					cog = ls[0]
					all_cogs.add(cog)
					for j, prot in enumerate(ls[1:]):
						sample_cog_proteins[original_samples[j]][cog] = sample_cog_proteins[original_samples[j]][
							cog].union(
							set(prot.split(', ')))

		header = [''] + [s for s in sorted(all_samples)]
		expanded_orthofinder_matrix_handle.write('\t'.join(header) + '\n')
		for c in sorted(all_cogs):
			printlist = [c]
			for s in sorted(all_samples):
				printlist.append(', '.join(sample_cog_proteins[s][c]))
			expanded_orthofinder_matrix_handle.write('\t'.join(printlist) + '\n')

		expanded_gcf_list_handle.close()
		expanded_orthofinder_matrix_handle.close()

def create_hmm_profiles(inputs):
	"""

	"""
	hg, sample_sequences, prot_seq_dir, prot_alg_dir, prot_hmm_dir, logObject = inputs

	hg_prot_fasta = prot_seq_dir + '/' + hg + '.faa'
	hg_prot_msa = prot_alg_dir + '/' + hg + '.msa.faa'
	hg_prot_hmm = prot_hmm_dir + '/' + hg + '.hmm'

	hg_prot_handle = open(hg_prot_fasta, 'w')
	for s in sample_sequences:
		hg_prot_handle.write('>' + s + '\n' + str(sample_sequences[s]) + '\n')
	hg_prot_handle.close()

	mafft_cmd = ['mafft', '--maxiterate', '1000', '--localpair', hg_prot_fasta, '>', hg_prot_msa]
	if logObject:
		logObject.info('Running mafft with the following command: %s' % ' '.join(mafft_cmd))
	try:
		subprocess.call(' '.join(mafft_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		if logObject:
			logObject.info('Successfully ran: %s' % ' '.join(mafft_cmd))
	except:
		if logObject:
			logObject.error('Had an issue running: %s' % ' '.join(mafft_cmd))
			logObject.error(traceback.format_exc())
		raise RuntimeError('Had an issue running: %s' % ' '.join(mafft_cmd))

	hmmbuild_cmd = ['hmmbuild', '--amino', '-n', hg, hg_prot_hmm, hg_prot_msa]
	if logObject:
		logObject.info('Running hmmbuild (from HMMER3) with the following command: %s' % ' '.join(hmmbuild_cmd))
	try:
		subprocess.call(' '.join(hmmbuild_cmd), shell=True, stdout=subprocess.DEVNULL,
						stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		if logObject:
			logObject.info('Successfully ran: %s' % ' '.join(hmmbuild_cmd))
	except:
		if logObject:
			logObject.error('Had an issue running: %s' % ' '.join(hmmbuild_cmd))
			logObject.error(traceback.format_exc())
		raise RuntimeError('Had an issue running: %s' % ' '.join(hmmbuild_cmd))

	if logObject:
		logObject.info('Constructed profile HMM for homolog group %s' % hg)

def popgen_analysis_of_hg(inputs):
	"""
	Helper function which is to be called from the runPopulationGeneticsAnalysis() function to parallelize population
	genetics analysis of each homolog group.

	:param inputs: list of inputs passed in by GCF.runPopulationGeneticsAnalysis().
	"""
	hg, codon_alignment_fasta, popgen_dir, plots_dir, comp_gene_info, hg_genes, bgc_sample, hg_prop_multi_copy, hg_order_scores, sample_population, logObject = inputs
	domain_plot_file = plots_dir + hg + '_domain.txt'
	position_plot_file = plots_dir + hg + '_position.txt'
	popgen_plot_file = plots_dir + hg + '_popgen.txt'
	plot_pdf_file = plots_dir + hg + '.pdf'

	domain_plot_handle = open(domain_plot_file, 'w')
	position_plot_handle = open(position_plot_file, 'w')
	popgen_plot_handle = open(popgen_plot_file, 'w')

	seqs = []
	bgc_codons = defaultdict(list)
	num_codons = None
	samples = set([])
	gene_lengths = []
	gene_locs = defaultdict(dict)
	core_counts = defaultdict(int)
	products = set([])
	with open(codon_alignment_fasta) as ocaf:
		for rec in SeqIO.parse(ocaf, 'fasta'):
			sample_id, gene_id = rec.id.split('|')
			if comp_gene_info[gene_id]['core_overlap']:
				core_counts['core'] += 1
			else:
				core_counts['auxiliary'] += 1
			products.add(comp_gene_info[gene_id]['product'])
			real_pos = 1
			seqs.append(list(str(rec.seq)))
			codons = [str(rec.seq)[i:i + 3] for i in range(0, len(str(rec.seq)), 3)]
			num_codons = len(codons)
			bgc_codons[rec.id] = codons
			samples.add(sample_id)
			for msa_pos, bp in enumerate(str(rec.seq)):
				if bp != '-':
					gene_locs[gene_id][real_pos] = msa_pos + 1
					real_pos += 1
			gene_lengths.append(len(str(rec.seq).replace('-', '')))

	is_core = False
	if float(core_counts['core']) / sum(core_counts.values()) >= 0.8: is_core = True

	median_gene_length = statistics.median(gene_lengths)

	variable_sites = set([])
	conserved_sites = set([])
	position_plot_handle.write(
		'\t'.join(['pos', 'num_seqs', 'num_alleles', 'num_gaps', 'maj_allele_freq']) + '\n')
	for i, ls in enumerate(zip(*seqs)):
		al_counts = defaultdict(int)
		for al in ls:
			if al != '-': al_counts[al] += 1
		maj_allele_count = max(al_counts.values())
		tot_count = sum(al_counts.values())
		num_seqs = len(ls)
		num_alleles = len(al_counts.keys())
		num_gaps = num_seqs - tot_count
		maj_allele_freq = float(maj_allele_count) / tot_count
		position_plot_handle.write(
			'\t'.join([str(x) for x in [i + 1, num_seqs, num_alleles, num_gaps, maj_allele_freq]]) + '\n')
		if maj_allele_freq <= 0.90:
			variable_sites.add(i)
		else:
			conserved_sites.add(i)
	position_plot_handle.close()

	differential_domains = set([])
	domain_positions_msa = defaultdict(set)
	domain_min_position_msa = defaultdict(lambda: 1e8)
	all_domains = set([])
	for gene in hg_genes[hg]:
		gene_start = comp_gene_info[gene]['start']
		gene_end = comp_gene_info[gene]['end']
		for domain in comp_gene_info[gene]['gene_domains']:
			domain_start = max(domain['start'], gene_start)
			domain_end = min(domain['end'], gene_end)
			domain_name = domain['aSDomain'] + '_|_' + domain['description']
			relative_start = domain_start - gene_start
			assert (len(gene_locs[gene]) + 3 >= (domain_end - gene_start))
			relative_end = min([len(gene_locs[gene]), domain_end - gene_start])
			domain_range = range(relative_start, relative_end)
			for pos in domain_range:
				msa_pos = gene_locs[gene][pos + 1]
				domain_positions_msa[domain_name].add(msa_pos)
				if domain_min_position_msa[domain_name] > msa_pos:
					domain_min_position_msa[domain_name] = msa_pos
			all_domains.add(domain['type'] + '_|_' + domain['aSDomain'] + '_|_' + domain['description'])

	domain_plot_handle.write('\t'.join(['domain', 'domain_index', 'min_pos', 'max_pos']) + '\n')
	for i, dom in enumerate(sorted(domain_min_position_msa.items(), key=itemgetter(1))):
		tmp = []
		old_pos = None
		for j, pos in enumerate(sorted(domain_positions_msa[dom[0]])):
			if j == 0:
				old_pos = pos - 1
			if pos - 1 != old_pos:
				if len(tmp) > 0:
					min_pos = min(tmp)
					max_pos = max(tmp)
					domain_plot_handle.write(
						'\t'.join([str(x) for x in [dom[0], i, min_pos, max_pos]]) + '\n')
				tmp = []
			tmp.append(pos)
			old_pos = pos
		if len(tmp) > 0:
			min_pos = min(tmp)
			max_pos = max(tmp)
			domain_plot_handle.write('\t'.join([str(x) for x in [dom[0], i, min_pos, max_pos]]) + '\n')
	domain_plot_handle.close()

	popgen_plot_handle.write('\t'.join(['pos', 'type']) + '\n')
	total_core_codons = 0
	total_variable_codons = 0
	nonsynonymous_sites = 0
	synonymous_sites = 0
	for cod_index in range(0, num_codons):
		first_bp = (cod_index + 1) * 3
		aa_count = defaultdict(int)
		aa_codons = defaultdict(set)
		cod_count = defaultdict(int)
		core = True
		for bgc in bgc_codons:
			cod = bgc_codons[bgc][cod_index]
			if '-' in cod or 'N' in cod:
				core = False
			else:
				cod_obj = Seq(cod)
				aa_count[str(cod_obj.translate())] += 1
				cod_count[cod] += 1
				aa_codons[str(cod_obj.translate())].add(cod)

		residues = len([r for r in aa_count if aa_count[r] >= 2])
		residues_with_multicodons = 0
		for r in aa_codons:
			supported_cods = 0
			for cod in aa_codons[r]:
				if cod_count[cod] >= 2: supported_cods += 1
			if supported_cods >= 2: residues_with_multicodons += 1

		maj_allele_count = max(cod_count.values())
		tot_valid_codons = sum(cod_count.values())
		maj_allele_freq = float(maj_allele_count) / tot_valid_codons

		nonsyn_flag = False;
		syn_flag = False
		if maj_allele_freq <= 0.9:
			total_variable_codons += 1
			if len(cod_count.keys()) > 1:
				if residues >= 2: nonsynonymous_sites += 1; nonsyn_flag = True
				if residues_with_multicodons >= 1: synonymous_sites += 1; syn_flag = True

		if core and not nonsyn_flag and not syn_flag: total_core_codons += 1
		if (nonsyn_flag and not syn_flag) or (not nonsyn_flag and syn_flag):
			type = 'S'
			if nonsyn_flag: type = 'NS'
			popgen_plot_handle.write('\t'.join([str(x) for x in [first_bp, type]]) + '\n')
	popgen_plot_handle.close()
	dn_ds = "NA"
	if synonymous_sites > 0: dn_ds = float(nonsynonymous_sites) / synonymous_sites

	rscript_plot_cmd = ["Rscript", RSCRIPT_FOR_CLUSTER_ASSESSMENT_PLOTTING, domain_plot_file, position_plot_file,
						popgen_plot_file,
						plot_pdf_file]
	if logObject:
		logObject.info('Running R-based plotting with the following command: %s' % ' '.join(rscript_plot_cmd))
	try:
		subprocess.call(' '.join(rscript_plot_cmd), shell=True, stdout=subprocess.DEVNULL,
						stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		if logObject:
			logObject.info('Successfully ran: %s' % ' '.join(rscript_plot_cmd))
	except Exception as e:
		if logObject:
			logObject.error('Had an issue running: %s' % ' '.join(rscript_plot_cmd))
			logObject.error(traceback.format_exc())
		raise RuntimeError(traceback.format_exc())

	tajima_results = popgen_dir + hg + '.tajima.txt'
	rscript_tajimaD_cmd = ["Rscript", RSCRIPT_FOR_TAJIMA, codon_alignment_fasta, tajima_results]
	if logObject:
		logObject.info('Running R pegas for calculating Tajima\'s D from codon alignment with the following command: %s' % ' '.join(
			rscript_tajimaD_cmd))
	try:
		subprocess.call(' '.join(rscript_tajimaD_cmd), shell=True, stdout=subprocess.DEVNULL,
						stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		if logObject:
			logObject.info('Successfully ran: %s' % ' '.join(rscript_tajimaD_cmd))
	except Exception as e:
		if logObject:
			logObject.error('Had an issue running: %s' % ' '.join(rscript_tajimaD_cmd))
			logObject.error(traceback.format_exc())
		raise RuntimeError(traceback.format_exc())

	tajimas_d = "NA"
	if os.path.isfile(tajima_results):
		with open(tajima_results) as otrf:
			for i, line in enumerate(otrf):
				if i == 4:
					try:
						tajimas_d = float(line.strip())
					except:
						pass

	prop_samples_with_cog = len(samples) / float(len(set(bgc_sample.values())))

	hg_info = [hg, '; '.join(products), hg_order_scores[hg], hg_prop_multi_copy[hg],
				median_gene_length, is_core, len(seqs), prop_samples_with_cog, tajimas_d, total_core_codons,
				total_variable_codons, nonsynonymous_sites, synonymous_sites, dn_ds, '; '.join(all_domains)]

	if sample_population:
		population_samples = defaultdict(set)
		for sp in sample_population.items():
			population_samples[sp[1]].add(sp[0])

		sample_seqs = {}
		with open(codon_alignment_fasta) as ocaf:
			for rec in SeqIO.parse(ocaf, 'fasta'):
				sample_seqs[rec.id.split('|')[0]] = str(rec.seq).upper()

		pairwise_differences = defaultdict(lambda: defaultdict(int))
		for i, s1 in enumerate(sample_seqs):
			for j, s2 in enumerate(sample_seqs):
				if i < j:
					for p, s1b in enumerate(sample_seqs[s1]):
						s2b = sample_seqs[s2][p]
						if s1b != s2b:
							pairwise_differences[s1][s2] += 1
							pairwise_differences[s2][s1] += 1

		pop_prop_with_cog = defaultdict(float)
		pops_with_cog = 0
		populations_order = []
		within_population_differences = []
		for pop in population_samples:
			pop_prop_with_cog[pop] = len(population_samples[pop].intersection(samples)) / len(
				population_samples[pop])
			if pop_prop_with_cog[pop] > 0: pops_with_cog += 1
			if len(population_samples[pop]) >= 2:
				within_pop = []
				for i, s1 in enumerate(population_samples[pop]):
					for j, s2 in enumerate(population_samples[pop]):
						if i < j:
							within_pop.append(pairwise_differences[s1][s2])
				within_population_differences.append(within_pop)
				populations_order.append(pop)

		anova_pval = "NA"
		if len(within_population_differences) >= 2:
			F, anova_pval = f_oneway(*within_population_differences)
		cog_population_info = [pops_with_cog,
							   '|'.join([str(x[0]) + '=' + str(x[1]) for x in pop_prop_with_cog.items()]),
							   anova_pval]
		hg_info += cog_population_info

	hg_stats_handle = open(popgen_dir + hg + '_stats.txt', 'w')
	hg_stats_handle.write('\t'.join([str(x) for x in hg_info]) + '\n')
	hg_stats_handle.close()

def create_codon_msas(inputs):
	"""
	Helper function which is to be called from the constructCodonAlignments() function to parallelize construction
	of codon alignments for each homolog group of interest in the GCF.
	:param inputs: list of inputs passed in by GCF.constructCodonAlignments().
	"""
	hg, gene_sequences, nucl_seq_dir, prot_seq_dir, prot_alg_dir, codo_alg_dir, logObject = inputs

	hg_nucl_fasta = nucl_seq_dir + '/' + hg + '.fna'
	hg_prot_fasta = prot_seq_dir + '/' + hg + '.faa'
	hg_prot_msa = prot_alg_dir + '/' + hg + '.msa.faa'
	hg_codo_msa = codo_alg_dir + '/' + hg + '.msa.fna'

	hg_nucl_handle = open(hg_nucl_fasta, 'w')
	hg_prot_handle = open(hg_prot_fasta, 'w')
	for s in gene_sequences:
		hg_nucl_handle.write('>' + s + '\n' + str(gene_sequences[s][0]) + '\n')
		hg_prot_handle.write('>' + s + '\n' + str(gene_sequences[s][1]) + '\n')
	hg_nucl_handle.close()
	hg_prot_handle.close()

	mafft_cmd = ['mafft', '--maxiterate', '1000', '--localpair', hg_prot_fasta, '>', hg_prot_msa]
	pal2nal_cmd = ['pal2nal.pl', hg_prot_msa, hg_nucl_fasta, '-output', 'fasta', '>', hg_codo_msa]

	if logObject:
		logObject.info('Running mafft with the following command: %s' % ' '.join(mafft_cmd))
	try:
		subprocess.call(' '.join(mafft_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		if logObject:
			logObject.info('Successfully ran: %s' % ' '.join(mafft_cmd))
	except Exception as e:
		if logObject:
			logObject.error('Had an issue running: %s' % ' '.join(mafft_cmd))
			logObject.error(traceback.format_exc())
		raise RuntimeError('Had an issue running: %s' % ' '.join(mafft_cmd))

	if logObject:
		logObject.info('Running PAL2NAL with the following command: %s' % ' '.join(pal2nal_cmd))
	try:
		subprocess.call(' '.join(pal2nal_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		if logObject:
			logObject.info('Successfully ran: %s' % ' '.join(pal2nal_cmd))
	except Exception as e:
		if logObject:
			logObject.error('Had an issue running: %s' % ' '.join(pal2nal_cmd))
			logObject.error(traceback.format_exc())
		raise RuntimeError('Had an issue running: %s' % ' '.join(pal2nal_cmd))

	if logObject:
		logObject.info('Achieved codon alignment for homolog group %s' % hg)
