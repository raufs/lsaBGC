import os
import sys
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
import logging
import subprocess
import statistics
from operator import itemgetter
from collections import defaultdict
import random
import traceback
import multiprocessing
import copy
import pysam
from scipy import stats
from ete3 import Tree
import itertools

def writeRefinedProteomes(s, sample_bgcs, refined_proteomes_outdir, logObject):
	try:
		refined_proteome_handle = open(refined_proteomes_outdir + s + '.faa', 'w')
		for bgc in sample_bgcs:
			with open(bgc) as obgc:
				for rec in SeqIO.parse(obgc, 'genbank'):
					for feature in rec.features:
						if feature.type == "CDS":
							lt = feature.qualifiers.get('locus_tag')[0]
							prot_seq = feature.qualifiers.get('translation')[0]
							refined_proteome_handle.write('>' + lt + '\n' + str(prot_seq) + '\n')
		refined_proteome_handle.close()
	except:
		logObject.warning("Had issues writing sample %s's BGC-specific proteome file. Will be ignored in OrthoFinder analysis.")

def getSampleRetentionSet(sample_retention_file):
	sample_retention_set = None
	if sample_retention_file:
		sample_retention_set = set([])
		with open(sample_retention_file) as osrf:
			for line in osrf:
				line = line.strip()
				sample_retention_set.add(line)

	return sample_retention_set

def determineOutliersByGeneLength(gene_sequences, logObject):
	filtered_gene_sequences = {}
	try:
		og_gene_nucl_seq_lens = []
		for g in gene_sequences:
			sample, gene = g.split('|')
			if len(gene.split('_')[0]) == 3:
				gene_nucl_seq = gene_sequences[g][0]
				gene_nucl_seq_len = len(gene_nucl_seq)
				og_gene_nucl_seq_lens.append(gene_nucl_seq_len)

		median_gene_nucl_seq_lens = statistics.median(og_gene_nucl_seq_lens)
		mad_gene_nucl_seq_lens = max(stats.median_absolute_deviation(og_gene_nucl_seq_lens), 25)

		for g in gene_sequences:
			gene_nucl_seq = gene_sequences[g][0]
			gene_nucl_seq_len = len(gene_nucl_seq)
			if abs(gene_nucl_seq_len-median_gene_nucl_seq_lens) <= mad_gene_nucl_seq_lens:
				filtered_gene_sequences[g] = gene_sequences[g]
	except:
		logObject.warning("Unable to filter gene sequences to remove outliers, possibly because there are too few sequences.")
		filtered_gene_sequences = gene_sequences
	return filtered_gene_sequences


def determineBGCSequenceSimilarityFromCodonAlignments(codon_alignments_file):
	valid_alleles = set(['A', 'C', 'G', 'T'])
	pair_seq_matching = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0)))
	sample_hgs = defaultdict(set)
	with open(codon_alignments_file) as ocaf:
		for line in ocaf:
			line = line.strip()
			hg, codon_alignment = line.split('\t')
			gene_sequences = {}
			allele_identifiers = {}
			with open(codon_alignment) as oca:
				for i, rec in enumerate(SeqIO.parse(oca, 'fasta')):
					gene_sequences[rec.id] = str(rec.seq).upper()
					allele_identifiers[rec.id] = i
					sample = rec.id.split('|')[0]
					sample_hgs[sample].add(hg)

			for i, g1 in enumerate(gene_sequences):
				s1 = g1.split('|')[0]
				g1s = gene_sequences[g1]
				for j, g2 in enumerate(gene_sequences):
					if i >= j: continue
					s2 = g2.split('|')[0]
					if s1 == s2: continue
					g2s = gene_sequences[g2]
					tot_comp_pos = 0
					g1_comp_pos = 0
					g2_comp_pos = 0
					match_pos = 0
					for pos, g1a in enumerate(g1s):
						g2a = g2s[pos]
						if g1a in valid_alleles or g2a in valid_alleles:
							tot_comp_pos += 1
							if g1a == g2a:
								match_pos += 1
						if g1a in valid_alleles:
							g1_comp_pos += 1
						if g2a in valid_alleles:
							g2_comp_pos += 1
					general_matching_percentage = float(match_pos)/float(tot_comp_pos)

					if pair_seq_matching[s1][s2][hg] < general_matching_percentage and pair_seq_matching[s2][s1][hg] < general_matching_percentage:
						pair_seq_matching[s1][s2][hg] = general_matching_percentage
						pair_seq_matching[s2][s1][hg] = general_matching_percentage

	bgc_pairwise_similarities = defaultdict(lambda: defaultdict(lambda: ["NA", "NA"]))
	for i, s1 in enumerate(sorted(sample_hgs)):
		for j, s2 in enumerate(sorted(sample_hgs)):
			if i >= j: continue
			common_hgs =  sample_hgs[s1].intersection(sample_hgs[s2])
			total_hgs = sample_hgs[s1].union(sample_hgs[s2])
			sum_pair_seq_matching = 0.0
			for hg in common_hgs:
				sum_pair_seq_matching += pair_seq_matching[s1][s2][hg]
			if len(common_hgs) > 0:
				bgc_pairwise_similarities[s1][s2] = [sum_pair_seq_matching / float(len(common_hgs)), float(len(common_hgs))/float(len(total_hgs))]
				bgc_pairwise_similarities[s2][s1] = [sum_pair_seq_matching / float(len(common_hgs)), float(len(common_hgs))/float(len(total_hgs))]
			else:
				bgc_pairwise_similarities[s1][s2] = ["NA", 0.0]
				bgc_pairwise_similarities[s2][s1] = ["NA", 0.0]

	return bgc_pairwise_similarities

def determineAllelesFromCodonAlignment(codon_alignment, max_mismatch=10, matching_percentage_cutoff=0.99):
	gene_sequences = {}
	allele_identifiers = {}
	with open(codon_alignment) as oca:
		for i, rec in enumerate(SeqIO.parse(oca, 'fasta')):
			gene_sequences[rec.id] = str(rec.seq).upper()
			allele_identifiers[rec.id] = i

	valid_alleles = set(['A', 'C', 'G', 'T'])
	pairs = []
	pair_matching = defaultdict(lambda: defaultdict(float))
	for i, g1 in enumerate(gene_sequences):
		g1s = gene_sequences[g1]
		for j, g2 in enumerate(gene_sequences):
			if i >= j: continue
			g2s = gene_sequences[g2]
			tot_comp_pos = 0
			g1_comp_pos = 0
			g2_comp_pos = 0
			match_pos = 0
			mismatch_pos = 0
			for pos, g1a in enumerate(g1s):
				g2a = g2s[pos]
				if g1a in valid_alleles and g2a in valid_alleles:
					if g1a != g2a:
						mismatch_pos += 1
				if g1a in valid_alleles or g2a in valid_alleles:
					tot_comp_pos += 1
					if g1a == g2a:
						match_pos += 1
				if g1a in valid_alleles:
					g1_comp_pos += 1
				if g2a in valid_alleles:
					g2_comp_pos += 1
			general_matching_percentage = float(match_pos)/float(tot_comp_pos)
			g1_matching_percentage = float(match_pos)/float(g1_comp_pos)
			g2_matching_percentage = float(match_pos)/float(g2_comp_pos)
			pair_matching[g1][g2] = general_matching_percentage
			if general_matching_percentage >= matching_percentage_cutoff or g1_matching_percentage >= matching_percentage_cutoff or g2_matching_percentage >= matching_percentage_cutoff:
				if mismatch_pos <= max_mismatch:
					pairs.append(sorted([g1, g2]))

	"""	
	Solution for single-linkage clustering taken from mimomu's repsonse in the stackoverflow page:
	https://stackoverflow.com/questions/4842613/merge-lists-that-share-common-elements?lq=1
	"""
	L = pairs
	LL = set(itertools.chain.from_iterable(L))
	for each in LL:
		components = [x for x in L if each in x]
		for i in components:
			L.remove(i)
		L += [list(set(itertools.chain.from_iterable(components)))]

	allele_cluster_min_id = {}
	for allele_cluster in L:
		gene_identifiers = set([])
		for gene in allele_cluster:
			gene_identifiers.add(allele_identifiers[gene])
		min_gi = min(gene_identifiers)
		allele_cluster_min_id[min_gi] = allele_cluster

	allele_clusters = defaultdict(set)
	for i, aci in enumerate(sorted(allele_cluster_min_id.keys())):
		for gene in allele_cluster_min_id[aci]:
			allele_clusters['Allele_Cluster_' + str(i+1)].add(gene)

	return [allele_clusters, pair_matching]

def cleanUpSampleName(original_name):
	return original_name.replace(' ', '_').replace(':', '_').replace('|', '_').replace('"', '_').replace("'", '_').replace("=", "_").replace('-', '_').replace('(', '').replace(')', '').replace('/', '').replace('\\', '')

def read_pair_generator_defunct(bam, region_string=None, start=None, stop=None):
	"""
    Function taken from: https://www.biostars.org/p/306041/
    Generate read pairs in a BAM file or within a region string.
    Reads are added to read_dict until a pair is found.
    """
	read_dict = defaultdict(lambda: [None, None])
	for read in bam.fetch(region_string, start=start, stop=stop):
		if not read.is_proper_pair or read.is_supplementary:
			continue
		qname = read.query_name
		if qname not in read_dict:
			if read.is_read1:
				read_dict[qname][0] = read
			else:
				read_dict[qname][1] = read
		else:
			if read.is_read1:
				yield read, read_dict[qname][1]
			else:
				yield read_dict[qname][0], read
			del read_dict[qname]

def read_pair_generator(bam, region_string, reference_length, max_insert_size=500):
	"""
    Function adapted from: https://www.biostars.org/p/306041/
    Generate read pairs in a BAM file or within a region string.
    Reads are added to read_dict until a pair is found.
    """

	read_reverse_counts = defaultdict(int)
	read_forward_counts = defaultdict(int)
	for read in bam.fetch(region_string):
		if read.is_supplementary: continue
		qname = read.query_name
		if read.is_reverse:
			read_reverse_counts[qname] += 1
		else:
			read_forward_counts[qname] += 1

	visited = set([])
	read_dict = defaultdict(lambda: [None, None])
	for read in bam.fetch(region_string):
		if read.is_supplementary: continue
		qname = read.query_name
		if read_reverse_counts[qname] > 1 or read_forward_counts[qname] > 1: continue
		if qname not in read_dict:
			if read.is_read1:
				read_dict[qname][0] = read
			else:
				read_dict[qname][1] = read
		else:
			# report proper pair paired-end reads, discard cases where both reads map to reference contig
			# but in an improper fashion.
			if read.is_proper_pair:
				if read.is_read1:
					yield read, read_dict[qname][1]
				else:
					yield read_dict[qname][0], read
			visited.add(qname)
			del read_dict[qname]

	for read in bam.fetch(region_string):
		qname = read.query_name
		if qname in visited: continue
		if read.is_supplementary or (not read.mate_is_unmapped): continue

		first_real_alignment_pos = None
		last_real_alignment_pos = None
		indel_positions = set([])
		match = 0
		aligned = 0
		for b in read.get_aligned_pairs(with_seq=True):
			if b[0] != None and b[1] != None and b[2] != None:
				if first_real_alignment_pos == None:
					first_real_alignment_pos = b[0]
				last_real_alignment_pos = b[0]
				if b[2].isupper():
					match += 1
				aligned += 1
			else:
				indel_positions.add(b[0])
		main_alignment_positions = set(range(first_real_alignment_pos, last_real_alignment_pos+1))
		has_indel = len(main_alignment_positions.intersection(indel_positions)) > 0

		matching_percentage = match/aligned
		positionally_checks_out = False
		if read.is_reverse:
			min_position = min(main_alignment_positions)
			positionally_checks_out = (min_position - max_insert_size) < 0
		else:
			max_position = max(main_alignment_positions)
			positionally_checks_out = (max_position + max_insert_size) > reference_length

		if (positionally_checks_out): # and (matching_percentage >= 0.95):
			yield read_dict[qname][0], read_dict[qname][1]

def getSpeciesRelationshipsFromPhylogeny(species_phylogeny, samples_in_gcf):
	samples_in_phylogeny = set([])
	t = Tree(species_phylogeny)
	for leaf in t:
		samples_in_phylogeny.add(str(leaf).strip('\n').lstrip('-'))

	pairwise_distances = defaultdict(lambda: defaultdict(float))
	for s1 in samples_in_gcf.intersection(samples_in_phylogeny):
		for s2 in samples_in_gcf.intersection(samples_in_phylogeny):
			try:
				s1_s2_dist = t.get_distance(s1, s2)
				pairwise_distances[s1][s2] = s1_s2_dist
			except:
				pass
	return ([pairwise_distances, samples_in_phylogeny])



def runBowtie2Alignments(bowtie2_reference, paired_end_sequencing_file, bowtie2_outdir, logObject, cores=1):
	"""
	Wrapper function for running Bowtie2 alignments to reference database/index

	:param bowtie2_reference: path to Bowtie2 reference/index
	:param paired_end_sequencing_file: tab delimited file with three columns: (1) sample name (2) path to forward
									   reads and (3) path to reverse reads
	:param bowtie2_outdir: Path to directory where Bowtie2 results should be written
	:param logObject: logging object for documentation
	:param cores: number of cores (total) to use. If more than 4 cores provided, then parallel Bowtie2 jobs with 4 cores
				  each will be started.
	"""
	bowtie2_cores = cores
	bowtie2_pool_size = 1
	if cores >= 4:
		bowtie2_cores = 4
		bowtie2_pool_size = int(cores / 4)

	try:
		bowtie2_inputs = []
		with open(paired_end_sequencing_file) as opesf:
			for line in opesf:
				line = line.strip()
				sample, frw_read, rev_read = line.split('\t')
				bowtie2_inputs.append([sample, frw_read, rev_read, bowtie2_reference, bowtie2_outdir, bowtie2_cores, logObject])
		p = multiprocessing.Pool(bowtie2_pool_size)
		p.map(bowtie2_alignment, bowtie2_inputs)
		p.close()
	except Exception as e:
		logObject.error("Issues in setting up and running Bowtie2 alignments.")
		logObject.error(traceback.format_exc())
		raise RuntimeError(traceback.format_exc())

def bowtie2_alignment(input_args):
	"""
	Function to perform Bowtie2 alignment of paired-end reads to a database/reference and post-processing of alignment
	file with samtools (e.g. convert to BAM format, sort BAM file, and index it).
	"""
	sample, frw_read, rev_read, bowtie2_reference, bowtie2_outdir, bowtie2_cores, logObject = input_args

	sam_file = bowtie2_outdir + sample + '.sam'
	bam_file = bowtie2_outdir + sample + '.bam'
	bam_file_sorted = bowtie2_outdir + sample + '.sorted.bam'
	#bam_file_filtered = bowtie2_outdir + sample + '.filtered.bam'
	#am_file_filtered_sorted = bowtie2_outdir + sample + '.filtered.sorted.bam'

	bowtie2_cmd = ['bowtie2', '--very-sensitive-local', '--no-unal', '-a', '-x', bowtie2_reference, '-U', frw_read, ',',
				   rev_read, '-S', sam_file, '-p', str(bowtie2_cores)]

	samtools_view_cmd = ['samtools', 'view', '-h', '-Sb', sam_file, '>', bam_file]
	samtools_sort_cmd = ['samtools', 'sort', '-@', str(bowtie2_cores), bam_file, '-o', bam_file_sorted]
	samtools_index_cmd = ['samtools', 'index', bam_file_sorted]

	try:
		run_cmd(bowtie2_cmd, logObject)
		run_cmd(samtools_view_cmd, logObject)
		run_cmd(samtools_sort_cmd, logObject)
		run_cmd(samtools_index_cmd, logObject)

		"""
		bam_handle = pysam.AlignmentFile(bam_file_sorted, 'rb')
		filt_bam_handle = pysam.AlignmentFile(bam_file_filtered, "wb", template=bam_handle)

		for read in bam_handle.fetch():
			if not read.is_proper_pair or read.is_supplementary: continue
			filt_bam_handle.write(read)

		filt_bam_handle.close()
		bam_handle.close()

		run_cmd(samtools_sort_cmd_2, logObject)
		run_cmd(samtools_index_cmd_2, logObject)
		"""

		os.system("rm -f %s %s" % (sam_file, bam_file)) # bam_file_sorted, bam_file_filtered, bam_file_sorted + '.bai'))
	except Exception as e:
		if bowtie2_outdir != "" and sample != "":
			os.system('rm -f %s/%s*' % (bowtie2_outdir, sample))
		raise RuntimeError(traceback.format_exc())


def createBGCGenbank(full_genbank_file, new_genbank_file, scaffold, start_coord, end_coord):
	"""
	Function to prune full genome-sized Genbank for only features in BGC of interest.

	:param full_genbank_file: Prokka generated Genbank file for full genome.
	:param new_genbank_file: Path to BGC specific Genbank to be created
	:param scaffold: Scaffold identifier.
	:param start_coord: Start coordinate.
	:param end_coord: End coordinate.
	"""
	try:
		ngf_handle = open(new_genbank_file, 'w')
		pruned_coords = set(range(start_coord, end_coord+1))
		with open(full_genbank_file) as ogbk:
			for rec in SeqIO.parse(ogbk, 'genbank'):
				if not rec.id == scaffold: continue
				original_seq = str(rec.seq)
				filtered_seq = ""
				if end_coord == len(original_seq):
					filtered_seq = original_seq[start_coord - 1:]
				else:
					filtered_seq = original_seq[start_coord - 1:end_coord]

				new_seq_object = Seq(filtered_seq)

				updated_rec = copy.deepcopy(rec)
				updated_rec.seq = new_seq_object

				updated_features = []
				for feature in rec.features:
					start = min([int(x) for x in str(feature.location)[1:].split(']')[0].split(':')])+1
					end = max([int(x) for x in str(feature.location)[1:].split(']')[0].split(':')])

					feature_coords = set(range(start, end + 1))
					if len(feature_coords.intersection(pruned_coords)) > 0:
						updated_start = start - start_coord + 1
						updated_end = end - start_coord + 1

						#flag1 = False; flag2 = False

						if end > end_coord:
							if feature.type == 'CDS': continue
							else: updated_end = end_coord - start_coord + 1#; flag1 = True
						if start < start_coord:
							if feature.type == 'CDS': continue
							else: updated_start = 1#; flag2 = True

						strand = 1
						if '(-)' in str(feature.location):
							strand = -1

						#if feature.type == 'CDS':
						#	print(str(full_genbank_file) + '\t' + str(flag1) + '\t' + str(flag2) + '\t' + feature.qualifiers.get('locus_tag')[0] + '\t' +
						#		  str(strand) + '\t' + str(updated_start) + '\t' + str(updated_end) + '\t' + str(len(filtered_seq[updated_start-1:updated_end]) / 3.0) +
						#		  '\t' + str(filtered_seq[updated_start - 1:updated_end]))

						updated_location = FeatureLocation(updated_start - 1, updated_end, strand=strand)
						updated_feature = copy.deepcopy(feature)

						updated_feature.location = updated_location
						updated_features.append(updated_feature)
				updated_rec.features = updated_features
				SeqIO.write(updated_rec, ngf_handle, 'genbank')
		ngf_handle.close()
	except Exception as e:
		raise RuntimeError(traceback.format_exc())

def parseGenbankAndFindBoundaryGenes(inputs):
	"""
	Function to parse Genbanks from Prokka and return a dictionary of genes per scaffold, gene to scaffold, and a
	set of genes which lie on the boundary of scaffolds.

	:param sample_genbank: Prokka generated Genbank file.
	:param distance_to_scaffold_boundary: Distance to scaffold edge considered as boundary.

	:return gene_to_scaffold: Dictionary mapping each gene's locus tag to the scaffold it is found on.
	:return scaffold_genes: Dictionary with keys as scaffolds and values as a set of genes found on that scaffold.
	:return boundary_genes: Set of gene locus tag ids which are found within proximity to scaffold edges.
	"""

	distance_to_scaffold_boundary = 500
	gene_location = {}
	scaffold_genes = defaultdict(set)
	boundary_genes = set([])
	gene_id_to_order = defaultdict(dict)
	gene_order_to_id = defaultdict(dict)

	sample, sample_genbank, sample_gbk_info = inputs
	with open(sample_genbank) as osg:
		for rec in SeqIO.parse(osg, 'genbank'):
			scaffold = rec.id
			scaffold_length = len(str(rec.seq))
			boundary_ranges = set(range(1, distance_to_scaffold_boundary+1)).union(set(range(scaffold_length-distance_to_scaffold_boundary, scaffold_length + 1)))
			gene_starts = []
			for feature in rec.features:
				if not feature.type == 'CDS': continue
				locus_tag = feature.qualifiers.get('locus_tag')[0]
				start = min([int(x) for x in str(feature.location)[1:].split(']')[0].split(':')])+1
				end = max([int(x) for x in str(feature.location)[1:].split(']')[0].split(':')])

				gene_location[locus_tag] = {'scaffold': scaffold, 'start': start, 'end': end}
				scaffold_genes[scaffold].add(locus_tag)

				gene_range = set(range(start, end+1))
				if len(gene_range.intersection(boundary_ranges)) > 0:
					boundary_genes.add(locus_tag)

				gene_starts.append([locus_tag, start])

			for i, g in enumerate(sorted(gene_starts, key=itemgetter(1))):
				gene_id_to_order[scaffold][g[0]] = i
				gene_order_to_id[scaffold][i] = g[0]

	sample_gbk_info[sample] = [gene_location, scaffold_genes, boundary_genes, gene_id_to_order, gene_order_to_id]

def calculateMashPairwiseDifferences(fasta_listing_file, outdir, name, sketch_size, cores, logObject, prune_set=None):
	"""
	Calculate MASH pairwise distances (estimated ANI) between FASTA files.

	:param fasta_listing_file: A tab-delimited listing file with two columns: (1) sample name (2) path to FASTA file
	:param outdir: The output directory where to write results
	:param name: Name of analysis scope
	:param sketch_size: Sketch size (a parameter of MASH)
	:param cores: Number of cores/threads to use
	:param logObject: The logging object.
	"""
	mash_db = outdir + name
	fastas = []
	fasta_to_name = {}
	try:
		with open(fasta_listing_file) as oflf:
			for line in oflf:
				line = line.strip()
				ls = line.split('\t')
				if prune_set != None and not ls[0] in prune_set: continue
				fastas.append(ls[1])
				fasta_to_name[ls[1]] = ls[0]
	except:
		error_message = "Had issues reading the FASTA listing file %s" % fasta_listing_file
		logObject.error(error_message)
		raise RuntimeError(error_message)

	mash_input_file = outdir + 'MASH_Input.txt'
	mash_input_handle = open(mash_input_file, 'w')
	mash_input_handle.write('\n'.join(fastas))
	mash_input_handle.close()

	# create mash database (using mash sketch)
	mash_sketch_cmd = ['mash', 'sketch', '-p', str(cores), '-s', str(sketch_size), '-o', mash_db, '-l', mash_input_file]
	logObject.info('Running mash sketch with the following command: %s' % ' '.join(mash_sketch_cmd))
	try:
		subprocess.call(' '.join(mash_sketch_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		logObject.info('Successfully ran: %s' % ' '.join(mash_sketch_cmd))
	except:
		error_message = 'Had an issue running: %s' % ' '.join(mash_sketch_cmd)
		logObject.error(error_message)
		raise RuntimeError(error_message)
	mash_db = mash_db + '.msh'

	try:
		assert (os.path.isfile(mash_db))
	except:
		error_message = "Had issue validating that MASH sketching worked properly, couldn't find: %s" % mash_db
		logObject.error(error_message)
		raise RuntimeError(error_message)

	# run mash distance estimation
	mash_dist_cmd = ['mash', 'dist', '-s', str(sketch_size), '-p', str(cores), mash_db, mash_db, '>',
					 outdir + name + '.out']
	logObject.info('Running mash dist with the following command: %s' % ' '.join(mash_dist_cmd))
	try:
		subprocess.call(' '.join(mash_dist_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
						executable='/bin/bash')
		logObject.info('Successfully ran: %s' % ' '.join(mash_dist_cmd))
	except:
		error_message = 'Had an issue running: %s' % ' '.join(mash_dist_cmd)
		logObject.error(error_message)
		raise RuntimeError(error_message)

	pairwise_distances = defaultdict(lambda: defaultdict(float))
	try:
		with open(outdir + name + '.out') as of:
			for line in of:
				line = line.strip()
				ls = line.split('\t')
				f1, f2, dist = ls[:3]
				dist = float(dist)
				n1 = fasta_to_name[f1]
				n2 = fasta_to_name[f2]
				pairwise_distances[n1][n2] = dist
	except:
		error_message = 'Had issues reading the output of MASH dist anlaysis in: %s.out' % outdir + name
		logObject.error(error_message)
		raise RuntimeError(error_message)
	return pairwise_distances

def parseOrthoFinderMatrix(orthofinder_matrix_file, relevant_gene_lts):
	"""
	Function to parse and return information from OrthoFinderV2 de novo homolog group identification.

	:param orthofinder_matrix: OrthoFinderV2 matrix Orthogroups.csv file
	:param relevant_gene_lts: set of all the relevant gene locus tag identifiers found in BGC Genbanks

	:return gene_to_hg: dictionary mapping gene locus tags to homolog group
	:return hg_genes: dictionary with set of gene locus tags for each homolog group
	:return hg_median_gene_counts: median copy count for each homolog group
	:return hg_multicopy_proportion: proportion of samples with homolog group which have multiple (paralogous) genes in the homolog group.
	"""
	gene_to_hg = {}
	hg_genes = defaultdict(set)
	hg_multicopy_proportion = defaultdict(lambda: 'NA')
	hg_median_gene_counts = defaultdict(lambda: 'NA')
	with open(orthofinder_matrix_file) as ofm:
		for i, line in enumerate(ofm):
			if i == 0: continue
			line = line.strip('\n')
			ls = line.split('\t')
			hg = ls[0]
			flag_in_bgc = False
			for sgs in ls[1:]:
				for g in sgs.split(', '):
					if g in relevant_gene_lts:
						flag_in_bgc = True
						gene_to_hg[g] = hg
						hg_genes[hg].add(g)
			if flag_in_bgc:
				gene_counts = []
				for sgs in ls[1:]:
					# critical for calculating homolog group stats, like median gene counts, multicopy proportion
					# use only genes from the original set of genomes used to conduct full orthofinder analysis.
					gene_counts.append(len([x for x in sgs.split(', ') if len(x.split('_')[0]) == 3]))

				hg_multicopy_proportion[hg] = float(sum([1 for x in gene_counts if x > 1])) / sum([1 for x in gene_counts if x > 0])
				hg_median_gene_counts[hg] = statistics.median(gene_counts)

	return ([gene_to_hg, hg_genes, hg_median_gene_counts, hg_multicopy_proportion])


def run_cmd(cmd, logObject, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
	"""
	Simple function to run a single command through subprocess with logging.
	"""
	logObject.info('Running the following command: %s' % ' '.join(cmd))
	try:
		subprocess.call(' '.join(cmd), shell=True, stdout=stdout, stderr=stderr, executable='/bin/bash')
		logObject.info('Successfully ran: %s' % ' '.join(cmd))
	except Exception as e:
		logObject.error('Had an issue running: %s' % ' '.join(cmd))
		logObject.error(traceback.format_exc())
		raise RuntimeError('Had an issue running: %s' % ' '.join(cmd))


def multiProcess(input):
	"""
	Genralizable function to be used with multiprocessing to parallelize list of commands. Inputs should correspond
	to space separated command (as list), with last item in list corresponding to a logging object handle for logging
	progress.
	"""
	input_cmd = input[:-1]
	logObject = input[-1]
	logObject.info('Running the following command: %s' % ' '.join(input_cmd))
	try:
		subprocess.call(' '.join(input_cmd), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,executable='/bin/bash')
		logObject.info('Successfully ran: %s' % ' '.join(input_cmd))
	except Exception as e:
		logObject.warning('Had an issue running: %s' % ' '.join(input_cmd))
		logObject.warning(traceback.format_exc())
		sys.stderr.write(traceback.format_exc())


def is_newick(newick):
	"""
	Function to validate if Newick phylogeny file is correctly formatted.
	"""
	try:
		t = Tree(newick)
		return True
	except:
		return False


def is_fasta(fasta):
	"""
	Function to validate if FASTA file is correctly formatted.
	"""
	try:
		with open(fasta) as of:
			SeqIO.parse(of, 'fasta')
		return True
	except:
		return False

def is_genbank(gbk):
	"""
	Function to check in Genbank file is correctly formatted.
	"""
	try:
		with open(gbk) as of:
			SeqIO.parse(of, 'genbank')
		return True
	except:
		return False

def createLoggerObject(log_file):
	"""
	Function which creates logger object.
	:param log_file: path to log file.
	:return: logging logger object.
	"""
	logger = logging.getLogger('task_logger')
	logger.setLevel(logging.DEBUG)
	# create file handler which logs even debug messages
	fh = logging.FileHandler(log_file)
	fh.setLevel(logging.DEBUG)
	# create console handler with a higher log level
	ch = logging.StreamHandler()
	ch.setLevel(logging.ERROR)
	# create formatter and add it to the handlers
	formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', "%Y-%m-%d %H:%M")
	fh.setFormatter(formatter)
	ch.setFormatter(formatter)
	# add the handlers to the logger
	logger.addHandler(fh)
	logger.addHandler(ch)

	# q = multiprocessing.Queue()
	# queue_listner = QueueListener(q, ch)
	# queue_listner.start()

	# logger.handlers[0].stream = sys.stderr
	return logger

def closeLoggerObject(logObject):
	"""
	Function which closes/terminates loggerObject.
	:param logObject: logging logger object to close
	"""
	handlers = logObject.handlers[:]
	for handler in handlers:
		handler.close()
		logObject.removeHandler(handler)

def logParameters(parameter_names, parameter_values):
	"""
	Function to log parameters of executable program to std.stderr
	"""
	for i, pv in enumerate(parameter_values):
		pn = parameter_names[i]
		sys.stderr.write(pn + ': ' + str(pv) + '\n')

def logParametersToFile(parameter_file, parameter_names, parameter_values):
	"""
	Function to log parameters of executable program to text file.
	"""
	parameter_handle = open(parameter_file, 'w')
	for i, pv in enumerate(parameter_values):
		pn = parameter_names[i]
		parameter_handle.write(pn + ': ' + str(pv) + '\n')
	parameter_handle.close()

def logParametersToObject(logObject, parameter_names, parameter_values):
	"""
	Function to log parameters of executable program to text file.
	"""
	for i, pv in enumerate(parameter_values):
		pn = parameter_names[i]
		logObject.info(pn + ': ' + str(pv))




