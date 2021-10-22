# -*- coding: utf-8 -*-

import pandas as pd 
import numpy as np
import networkx as nx
from typing import Dict, List, Tuple, Any
import time
from collections import Counter
from itertools import product
import time

from .transformations import TRANSFORMATIONS
from .cli import get_args

#TODO update new arg names here
"""
This program partitions an entity set according to a single pairwise distance metric
and some desired threshold the partitions should fullfill.
The program seeks maximum distance between partitions. If the metric and desired 
threshold imply minimization you should designate the ('-tf', '--transformation')
parameter and specify either the one-minus or inverse transformation. The program 
converts the designated threshold the same way as the metric.
If for example a pair of entities have no distance between them (are identical)
when the metric is 1.0, and the desired threshold is 0.3, you would specify the threshold
-th 0.3 or --threshold 0.3, and then specify the desired transformation 
('-tf', '--transformation') such as -tf one-minus.
The entity/meta file can contain a priority designator and a label designator 
For example:
>entity_identifier1|exp=1|class=label1
>entity_identifier2|exp=0|class=label2
the priority name and label name should be designated using the appropriate parameters.
In this case you would specify the priority name -pn experimental and the label name 
-ln class
For the full list of parameters, run graph_part.py --help
Example usage:
python graph_part.py 
    -ff ../../data/sequences/raw_data.fasta 
    -ef ../../data/edgefiles/ggs_default_gpia2_edges 
    -mc 2
    -th 0.31 
    -pa 5 
    -tf one-minus 
    -pn experimental
    -ln positive 
    -of gpia_gps_part_identity2.csv
Author(s): Magnús Halldór Gíslason.
           Developed in close collaboration with 
           José Juan Almagro Armenteros and Henrik Nielsen.
For bug reporting contact mhgislason@gmail.com
(CC BY-NC 4.0) 
You are free to:
Share — copy and redistribute the material in any medium or format
Adapt — remix, transform, and build upon the material
Under the following terms:
Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made. 
You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.
NonCommercial — You may not use the material for commercial purposes.
No additional restrictions — You may not apply legal terms or technological measures that legally restrict others 
from doing anything the license permits.
see:
https://creativecommons.org/licenses/by-nc/4.0/
https://creativecommons.org/licenses/by-nc/4.0/legalcode
"""


def process_csv(line: str) -> Tuple[str, dict]:
    """ NOT IMPLEMENTED """
    raise NotImplementedError('Graph-Part does not support starting from .csv yet.')
    yield None, None

def process_fasta(line: str, priority_name:str, labels_name:str, labels: dict) -> Tuple[str, dict]:
    """ Processes a fasta header lines or fasta meta data lines, if you will.
        Only supports interleaved fasta with > initialized header lines.
        Separate metadata with pipes | or colons :, whitespace between separators are ignored. 
        Some fasta files use the dash - as a separator. The dash is also used as an isoform indicator
        in accension numbers the dash separator. The option space dash space or [ - ] is implemented, but untested. """
    spl = line.strip().split('|')
    if ' - ' in spl[0]:
       spl = line.strip().split(' - ')
    if ':' in spl[0]:
        spl = line.strip().split(':')

    AC = spl[0].strip()[1:]
    priority = False
    label = '0'
    for s in spl[1:]:
        if '=' in s:
            param_spl = s.split('=')
            if param_spl[0] == priority_name:
                try:
                    priority = int(param_spl[1])==1
                except ValueError or TypeError:
                    raise TypeError("The input interpreted as priority designation did not conform as expected. Value interpeted: %r, Line: %r" % (param_spl[1], line))
            elif param_spl[0] == labels_name:
                label = str(param_spl[1].strip())

    if label not in labels:
        labels[label] = {'val':len(labels), 'num':0}
    labels[label]['num'] += 1

    label = labels[label]['val']

    node_data = {
        'priority': priority,
        'label-val': label
    }
    return AC, node_data


def load_entities(entity_fp: str, priority_name: str, labels_name: str):
    part_graph = nx.Graph()
    full_graph = nx.Graph()

    labels = {}
    with open(entity_fp) as inf:
        processing_as = None
        for line in inf:
            if '>' in line and processing_as != 'csv':
                AC, node_data = process_fasta(line, priority_name, labels_name, labels)
                processing_as = 'fasta'
            elif processing_as == 'fasta':
                continue
            else:
                AC, node_data = process_csv(line)
                processing_as = 'csv'

            full_graph.add_node(AC)
            nx.set_node_attributes(full_graph, {AC:node_data})
            
            part_graph.add_node(AC)

    return full_graph, part_graph, labels


def partition_assignment(cluster_vector, label_vector, n_partitions, n_class):
    ''' Function to separate proteins into N partitions with balanced classes 
        Courtesy of José Juan Almagro Armenteros '''
    
    # Unique cluster number
    u_cluster = np.unique(cluster_vector)
    
    # Initialize matrices
    loc_number = np.ones((n_partitions,n_class))
    cl_number = np.zeros(cluster_vector.shape[0])
    
    for i in u_cluster:
        # Extract the labels for the proteins in that cluster
        positions = np.where(cluster_vector == i)
        cl_labels = label_vector[positions]
        
        # Count number of each class
        u, count = np.unique(cl_labels, return_counts=True)
        
        u = u.astype(np.int32)
        temp_loc_number = np.copy(loc_number)
        temp_loc_number[:,u] += count
        loc_per = loc_number/temp_loc_number
        best_group = np.argmin(np.sum(loc_per,axis=1))
        loc_number[best_group,u] += count
        
        # Store the selected partition
        cl_number[positions] = best_group
    
    return cl_number
        

def partition_data(full_graph: nx.classes.graph.Graph, 
                   part_graph: nx.classes.graph.Graph,
                   labels: dict,
                   threshold: float,
                   nr_of_parts: int,
                   mode: int):
    part_size = full_graph.number_of_nodes()//nr_of_parts

    label_limits = np.array([x[1]['lim'] for x in sorted(labels.items(), key=lambda x:x[1]['val'] )])
    print(part_size, label_limits)
    
    count = 0
    ## AC, cluster, label
    acs = []
    clusters = []
    labels = []
    print("Initialization mode", mode)

    ## Initialize the initialization
    for ind, AC in enumerate(part_graph.nodes()):
        label_counts = np.zeros(len(label_limits), dtype=int)
        label_counts[full_graph.nodes[AC]['label-val']] = 1
        cluster_nr = ind
        
        if mode == 'simple':
            d = full_graph.nodes[AC]
            acs.append(AC)
            clusters.append(cluster_nr)
            labels.append(d['label-val'])
        nx.set_node_attributes(part_graph, {
            AC:{
                'cluster': cluster_nr,
                'C-size': 1,
                'label-counts': label_counts
            }
        })

    ## Restricted closest neighbour linkage
    if mode in ['slow-nn', 'fast-nn']:
        ## Linking entities, if restrictions allow
        for qry, lib, data in sorted(full_graph.edges(data=True), key=lambda x: x[2]['metric']):
            if data['metric'] > threshold:
                ## No need to continue if threshold reached.
                break
            
            if part_graph.has_edge(qry, lib):
                ## Update edge if it exists
                if part_graph[qry][lib]['metric'] > data['metric']:
                    nx.set_edge_attributes(part_graph,{(qry,lib):data['metric']}, 'metric')
                continue
            
            if part_graph.nodes[qry]['cluster'] == part_graph.nodes[lib]['cluster']:
               continue

            ## RESTRICTIONS!
            if part_graph.nodes[qry]['C-size'] >= part_size:
                continue
            if part_graph.nodes[lib]['C-size'] >= part_size:
                continue
            if (part_graph.nodes[qry]['label-counts']+part_graph.nodes[lib]['label-counts'] >= label_limits).any():
                continue
            
            ## Add edge and update mini-cluster
            attr = part_graph.nodes[qry]
            if attr['cluster'] != part_graph.nodes[lib]['cluster'] or mode == 'fast-nn':
                attr['C-size'] += part_graph.nodes[lib]['C-size']
                attr['label-counts'] += part_graph.nodes[lib]['label-counts']
            nx.set_node_attributes(part_graph, {qry:attr})
            part_graph.add_edge(qry, lib, metric=data['metric'])

            for descendant in nx.descendants(part_graph, qry):
                nx.set_node_attributes(part_graph, {descendant:attr})

            count += 1
            if count % 10000 == 0:
                print("edges:", part_graph.number_of_edges()) 
                print (attr, data)
        #with open('graph_part_miniclusters.txt','w+') as outf:
        for cc_nr, cc in enumerate(nx.connected_components(part_graph)):
            for n in cc:
                d = full_graph.nodes[n]
                acs.append(n)
                clusters.append(cc_nr)
                labels.append(d['label-val'])
                    #outf.write("%s,%d\n" % (n,cc_nr))

    acs = np.array(acs)
    clusters = np.array(clusters)
    labels = np.array(labels)
    print(len(np.unique(labels)))
    partitioning = partition_assignment(clusters, labels, nr_of_parts, len(np.unique(labels)))
    for ind, p in enumerate(partitioning):
        attr = part_graph.nodes[acs[ind]]
        attr['cluster'] = p
        nx.set_node_attributes(part_graph,{acs[ind]:attr})


def remover(full_graph: nx.classes.graph.Graph, 
            part_graph: nx.classes.graph.Graph, 
            threshold:float, 
            json_dict: Dict[str, Any],
            move_to_most_neighbourly:bool = True, 
            ignore_priority:bool = True,
            simplistic_removal:bool = True):

    if ignore_priority:
        json_dict['removal_step_1'] = {}
        dict_key = 'removal_step_1'
    else:
        json_dict['removal_step_2'] = {}
        dict_key = 'removal_step_2'
    
    print("Min-threshold", "\t", "#Entities", "\t", "#Edges", "\t", "Connectivity", "\t", "#Problematics", "\t", "#Relocated", "\t", "#To-be-removed")
    removing_round = 0
    while True:
        between_connectivity = {}
        min_oc_wth= 1
        number_moved = 0
        for n,d in full_graph.nodes(data=True):
            neighbours = nx.neighbors(full_graph,n)
            neighbour_clusters = Counter((part_graph.nodes[nb]['cluster'] for nb in nx.neighbors(full_graph,n) if full_graph[n][nb]['metric'] < threshold))
            cluster = part_graph.nodes[n]['cluster']
            nb_sc_wth = []
            nb_oc_wth = []
            
            ## FIRST MOVE NODE TO CLUSTER WITH MOST NEIGHBOURS
            if move_to_most_neighbourly:
                if len(neighbour_clusters) > 0:
                    most_neighbourly_cluster = max(neighbour_clusters.items(), key=lambda x:x[1])[0]
                    if most_neighbourly_cluster != cluster:
                        part_graph.nodes[n]['cluster'] = most_neighbourly_cluster
                        number_moved += 1
            
            if ignore_priority and full_graph.nodes[n]['priority']:
                between_connectivity[n] = 0
                continue

            for neighbour in neighbours:
                nb_cluster = part_graph.nodes[neighbour]['cluster']
                if nb_cluster == cluster and full_graph[n][neighbour]['metric'] < threshold and not simplistic_removal:
                    ## The more complex removal criterion. This was worse for GPI anchors. Haven't checked for Subnuclear
                    nb_sc_wth.append(full_graph[n][neighbour]['metric'])
                elif nb_cluster != cluster and full_graph[n][neighbour]['metric'] < threshold:
                    min_oc_wth = min(min_oc_wth, full_graph[n][neighbour]['metric'])
                    nb_oc_wth.append(full_graph[n][neighbour]['metric'])

            ## The more complex additional connectivity criterion, will be empty with simple_removal == True        
            distances = [x for x in (sum(x_) for x_ in product(nb_sc_wth, nb_oc_wth)) if x >= threshold] 
            
            distances += nb_oc_wth

            between_connectivity[n] = len(distances)
            
        nx.set_node_attributes(full_graph, between_connectivity, 'between_connectivity')
        bc_sum = np.sum(np.fromiter((d['between_connectivity'] for n,d in full_graph.nodes(data=True)),int))
        bc_count = np.sum(np.fromiter((1 for n,d in full_graph.nodes(data=True) if d['between_connectivity'] > 0),int))

        removing_round += 1
        number_to_remove = int(bc_count*np.log10(removing_round)/100)+1 # int(bc_count*0.01)+1
        ## Remove 1% + 1 of the most problematic entities
        remove_these = [x[0] for x in sorted(((n,d['between_connectivity']) for n,d in full_graph.nodes(data=True) if d['between_connectivity'] > 0), key=lambda x:x[1], reverse=True)[:number_to_remove]]
        
        print(round(min_oc_wth,7), "\t\t", full_graph.number_of_nodes(), "\t\t", full_graph.number_of_edges(), "\t\t", bc_sum, "\t\t", bc_count, "\t\t", number_moved, "\t\t", len(remove_these))
        
        json_dict[dict_key][removing_round] = {
                                                "Min-threshold": round(min_oc_wth,7) ,
                                                "#Entities": full_graph.number_of_nodes(),
                                                "#Edges": full_graph.number_of_edges(),
                                                "Connectivity": int(bc_sum), 
                                                "#Problematics": int(bc_count), 
                                                "#Relocated": number_moved, 
                                                "#To-be-removed":len(remove_these)
                                                }

        full_graph.remove_nodes_from(remove_these)
        # If we've removed the last problematic entities, we stop
        if full_graph.number_of_nodes()==0 or bc_sum==0 or len(remove_these) == bc_count:
            break

def score_partitioning(df:pd.core.frame.DataFrame) -> float:
    s0 = df.shape[0]
    s1 = df.shape[1]
    return float((df.product(axis=1)**(1/s1)).product()**(1/s0))

def display_results(
    part_graph: nx.classes.graph.Graph, 
    full_graph: nx.classes.graph.Graph,
    labels: dict,
    nr_of_parts: int) -> Tuple[pd.core.frame.DataFrame, pd.core.frame.DataFrame]:
    """ """
    df = pd.DataFrame(((d) for n,d in full_graph.nodes(data=True)))
    df['cluster'] = [part_graph.nodes[n]['cluster'] for n in full_graph.nodes()]

    # It can happen that removal completely removed one partition.
    # In this case, we need to report back an error
    if len(df['cluster'].unique()) < nr_of_parts:
        error_string = f'''
        Impossible to generate the desired {nr_of_parts} partitions at the current partitioning threshold.
        Removal of sequences to achieve separation results in loss of {nr_of_parts-len(df['cluster'].unique())} complete partitions.
        '''
        raise RuntimeError(error_string)

    df['AC'] = [n for n in full_graph.nodes()]
    result = df.groupby(['cluster','label-val'])['AC'].count().reset_index().pivot_table(values='AC',columns=['label-val'],index=['cluster']).T
    df.set_index('AC', inplace=True)
    result['label'] = ''
    for l in labels:
        result.loc[labels[l]['val'], 'label'] = l
        result['mean'] = result[list(range(nr_of_parts))].mean(axis=1)
        result['count'] = result[list(range(nr_of_parts))].sum(axis=1)
    print(result)
    print()
    print("Partitioning score:", score_partitioning(result[range(nr_of_parts)]))
    print()
    return df, result
    

def removal_needed(
    part_graph: nx.classes.graph.Graph, 
    full_graph: nx.classes.graph.Graph,
    threshold: float) -> bool:
    """ """
    min_between = float('Inf')
    for qry, lib, fed in full_graph.edges(data=True):
        if part_graph.nodes[qry]['cluster'] != part_graph.nodes[lib]['cluster']:
            if fed['metric'] < min_between:
                min_between = fed['metric']
            if min_between < threshold:
                print ("! ", qry, lib, fed, " !")
                return True
    return False

def main():

    # in this dict we collect everything that we want to report.
    json_dict = {}
    
    s = time.perf_counter()
    json_dict['time_script_start'] = s
    
    args = get_args()
    json_dict['config'] = vars(args)

    allow_moving = not args.no_moving
    removal_type = not args.remove_same
    try:
        with open(args.out_file, 'w+') as outf:
            pass
    except:
        raise ValueError("Output file path (-of/--out-file) improper or nonexistent.") 
    
    threshold = TRANSFORMATIONS[args.transformation](args.threshold)
    json_dict['config']['threshold_transformed'] = threshold

    ## End of parameter validation

    ## Processing starts here:

    ## Load entities/samples as networkx graphs. labels contains label metadata.
    full_graph, part_graph, labels = load_entities(args.fasta_file, args.priority_name, args.labels_name)

    for l in labels:
        """ Find the expected number of entities labelled l in any partition """
        labels[l]['lim'] = labels[l]['num']//args.partitions

    ## Let's see the initial label distribution
    print(pd.DataFrame(labels).T)
    json_dict['labels_start'] = labels


    ## Get the edges
    if args.load_checkpoint_path is not None:
        print('Loading edge weights from previously saved graph. Provided alignment options will be ignored, threshold will be updated.')
        # load from previous checkpoint
        checkpoint_graph = pickle.load(full_graph, open(args.load_checkpoint_path+'.pickle', 'rb'))
        # filter edges to match defined threshold - need not be the same as when checkpoint was saved.
        for qry, lib, data in checkpoint_graph.edges(data=True):
            if data['metric'] > threshold:
                full_graph.add_edge(qry, lib, metric=data['metric'])

    elif args.alignment_mode == 'precomputed':
        from .precomputed_utils import load_edge_list
        print('Parsing edge list.')
        load_edge_list(args.edge_file, full_graph, args.transformation, threshold, args.metric_column)
        elapsed_align = time.perf_counter() - s
        print(f"Edge list parsing executed in {elapsed_align:0.2f} seconds.")

    elif args.alignment_mode == 'mmseqs2':
        from .mmseqs_utils import generate_edges_mmseqs
        generate_edges_mmseqs(args.fasta_file, full_graph, args.transformation, threshold, args.threshold, denominator=args.denominator, delimiter='|', is_nucleotide=args.nucleotide)
        elapsed_align = time.perf_counter() - s
        print(f"Pairwise alignment executed in {elapsed_align:0.2f} seconds.")    

    elif args.alignment_mode == 'needle' and args.threads>1:
        from .needle_utils import generate_edges_mp
        print('Computing pairwise sequence identities.')
        generate_edges_mp(args.fasta_file, full_graph, args.transformation, threshold, denominator=args.denominator, n_chunks=args.chunks, n_procs=args.threads, triangular=args.triangular, delimiter='|', 
                            is_nucleotide=args.nucleotide, gapopen=args.gapopen, gapextend=args.gapextend, endweight=args.endweight, endopen=args.endopen, endextend=args.endextend, matrix=args.matrix)
        elapsed_align = time.perf_counter() - s
        print(f"Pairwise alignment executed in {elapsed_align:0.2f} seconds.")

    elif args.alignment_mode == 'needle':
        from .needle_utils import generate_edges
        print('Computing pairwise sequence identities.')
        generate_edges(args.fasta_file,full_graph, args.transformation, threshold, denominator=args.denominator, delimiter='|',
                            is_nucleotide=args.nucleotide, gapopen=args.gapopen, gapextend=args.gapextend, endweight=args.endweight, endopen=args.endopen, endextend=args.endextend, matrix=args.matrix)
        elapsed_align = time.perf_counter() - s
        print(f"Pairwise alignment executed in {elapsed_align:0.2f} seconds.")

    else:
        raise NotImplementedError('Encountered unspecified alignment mode. This should never happen.')


    ## Let's look at the number of edges
    print("Full graph nr. of edges:", full_graph.number_of_edges())

    json_dict['graph_edges_start'] = full_graph.number_of_edges()
    json_dict['time_edges_complete'] = time.perf_counter()

    if args.save_checkpoint_path is not None:
        import pickle
        pickle.dump(full_graph, open(args.save_checkpoint_path+'.pickle', 'wb'))
    
    ## Finally, let's partition this
    partition_data(full_graph, part_graph, labels, threshold, args.partitions, args.initialization_mode)

    df, result = display_results(part_graph, full_graph, labels, args.partitions)
    df.to_csv(args.out_file + "pre-removal")
    print('Currently have this many samples:', full_graph.number_of_nodes())

    json_dict['partitioning_pre_removal'] = result.to_json()
    json_dict['samples_pre_removal'] = full_graph.number_of_nodes()
    json_dict['score_pre_removal'] = score_partitioning(result[range(args.partitions)])

    
    ## Check if we need to remove any
    if removal_needed(part_graph, full_graph, threshold):     
        print('Need to remove! Currently have this many samples:', full_graph.number_of_nodes())

        remover(full_graph, part_graph, threshold, json_dict, allow_moving, True, removal_type)    

    if removal_needed(part_graph, full_graph, threshold):   
        print('Need to remove priority! Currently have this many samples:', full_graph.number_of_nodes())
        remover(full_graph, part_graph, threshold, json_dict, allow_moving, False, removal_type)    

    print('After removal we have this many samples:', full_graph.number_of_nodes())


    df, result = display_results(part_graph, full_graph, labels, args.partitions)

    json_dict['partitioning_after_removal'] = result.to_json()
    json_dict['samples_after_removal'] = full_graph.number_of_nodes()
    json_dict['score_after_removal'] = score_partitioning(result[range(args.partitions)])

    if removal_needed(part_graph, full_graph, threshold):
        print ("Something is wrong! Removal still needed!")
        json_dict['removal_needed_end'] = True
    else:
        json_dict['removal_needed_end'] = False

    ## clustering to outfile. This will probably change...
    df.to_csv(args.out_file)

    elapsed = time.perf_counter() - s
    json_dict['time_script_complete'] = time.perf_counter()

    print(f"Graph-Part executed in {elapsed:0.2f} seconds.")

    import json
    import os
    #import ipdb; ipdb.set_trace()
    json.dump(json_dict, open(os.path.splitext(args.out_file)[0]+'_report.json','w'))

if __name__ == "__main__":
    main()
