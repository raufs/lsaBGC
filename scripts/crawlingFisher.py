#!/usr/bin/env python

import os
import sys
import argparse
from scipy import stats
from collections import defaultdict
from ete3 import Tree
import numpy as np

def p_adjust_bh(p):
	"""
	Benjamini-Hochberg p-value correction for multiple hypothesis testing.
	"""
	p = np.asfarray(p)
	by_descend = p.argsort()[::-1]
	by_orig = by_descend.argsort()
	steps = float(len(p)) / np.arange(len(p), 0, -1)
	q = np.minimum(1, np.minimum.accumulate(steps * p[by_descend]))
	return q[by_orig]

def read_orthofile(homolog_matrix_file):
	try:
		col_to_sample = {}
		homolog_info = {}
		for i, line in enumerate(open(homolog_matrix_file)):
			line = line.rstrip('\n')
			ls = line.split('\t')
			if i == 0:
				for j, val in enumerate(ls[1:]):
					col_to_sample[j] = len(val.split(','))
			else:
				homolog_info[ls[0]] = ls[1:]
		return [col_to_sample, homolog_info]
	except:
		sys.stderr.write("Problem parsing homolog matrix! Please check for formatting. Exiting now ...")
		raise RuntimeError


def determine_pvalue(node_id, ortho_info, col_to_sample, all_children, all_tree_samples):
	node_hgs = []
	pvalues = []
	for hg in ortho_info:
		node_hg_counts = sum([1 for i, v in enumerate(ortho_info[hg]) if col_to_sample[i] in all_children and v > 0])
		node_no_hg_counts = sum([1 for i, v in enumerate(ortho_info[hg]) if col_to_sample[i] in all_children and v == 0])
		other_hg_counts = sum([1 for i, v in enumerate(ortho_info[hg]) if not col_to_sample[i] in all_children and v > 0 and col_to_sample[i] in all_tree_samplesl])
		other_no_hg_counts = sum([1 for i, v in enumerate(ortho_info[hg]) if not col_to_sample[i] in all_children and v == 0 and col_to_sample[i] in all_tree_samples])
		odds, pval = stats.fisher_exact([[node_hg_counts, other_hg_counts], [node_no_hg_counts, other_no_hg_counts]])
		node_prop = float(node_hg_counts)/float(node_hg_counts + node_no_hg_counts)
		other_prop = float(other_hg_counts)/float(other_hg_counts + other_no_hg_counts)
		node_hgs.append([node_id, hg, '; '.join(all_children), node_prop, other_prop])
		pvalues.append(pval)
	return([node_hgs, pvalues])

def is_innernode(i):
	if i.startswith("node"):
		return True
	try:
		float(i); return True
	except:
		return False


def recursively_get_children(direct_children_map, curr_node):
	""" feeling like fibonacci """
	children = set([])
	direct_children = direct_children_map[curr_node]
	for child in direct_children:
		if is_innernode(child):
			children = children.union(recursively_get_children(direct_children_map, child))
		else:
			children.add(child)
	return children


def parse_phylogeny(tree):
	try:
		t = Tree(tree, format=1)
		direct_children = defaultdict(set)
		for node in t.traverse("postorder"):
			try:
				parent_name = node.up.name
				direct_children[parent_name].add(node.name)
			except: pass
		return direct_children
	except:
		sys.stderr.write("Problem parsing phylogeny! Please check input newick file. Exiting now ...")
		raise RuntimeError


def crawlingFisher(tree, homolog_matrix, output, min_proportion):
	try:
		assert (os.path.isfile(tree) and os.path.isfile(homolog_matrix))
	except:
		sys.stderr.write("Either phylogeny or homolog matrix does not exist. Exiting now ..."); raise RuntimeError

	direct_children = parse_phylogeny(tree)
	col_to_sample, homolog_info = read_orthofile(homolog_matrix)

	output = os.path.abspath(output)

	try:
		assert (not os.path.isfile(output))
	except:
		sys.stderr.write("Output file already exists. Please remove/rename."); raise RuntimeError

	out = open(output, 'w')
	out.write('hg\tnode\tchildren\tadj_pvalue\tnode_prop\tother_prop\n')

	all_pvalues = []
	all_node_hgs = []

	all_tree_samples = set([])
	for leaf in Tree(tree):
		all_tree_samples.add(str(leaf).strip('\n').lstrip('-'))

	for par in direct_children:
		all_children = recursively_get_children(direct_children, par)
		if len(all_children) >= 5:
			node_hgs, pvalues = node_specific_hgs(par, homolog_info, col_to_sample, all_children, all_tree_samples)
			all_node_hgs += node_hgs
			all_pvalues += node_pvalues
	out.close()

	adj_pvalues = p_adjust_bh()
	for i, data in enumerate(all_node_hgs):
		if adj_pvalues[i] < 0.05 and data[3] >= min_proportion:
			out.write('\t'.join([str(x) for x in [data[1], data[0], data[2], adj_pvalues[i], data[3], data[4]]]) + '\n')
	out.close()

if __name__ == '__main__':
	# Pull out the arguments.
	parser = argparse.ArgumentParser(
		description=""" This program crawls up a phylogenetic tree and runs Fisher's exact test for each homolog group, then does multiple testings correction using Benjamini-Hochberg.""")
	parser.add_argument('-t', '--tree', help='Phylogenetic tree in Newick format. Inner nodes must be named!',
						required=True)
	parser.add_argument('-i', '--homolog_matrix',
						help='Homolog matrix showing homolog copy-count across samples in phylogeny.', required=True)

	parser.add_argument('-o', '--output', help="Output iTol dataset file.", required=True)
	parser.add_argument('-p', '--min_proportion', type=float, help="Proportion of clade members which need to have at least one instance of the HG.", default=0.8, required=False)
	args = parser.parse_args()

	crawlingFisher(args.tree, args.homolog_matrix, args.output, args.min_proportion)