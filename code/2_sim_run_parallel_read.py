#################################################################################################
# 1. Import libraries and set up output folders
#################################################################################################
# Import Python libraries
import numpy as np  
import pandas as pd 
import networkx as nx 
import random as rng 
import os
import sys
import geopy.distance as gp
import logging as lg
from plotnine import *
from scipy import stats

import multiprocessing as mp
from multiprocessing import Pool

#################################################################################################
# 1. Initialize Parameters
#################################################################################################
#Determine if the machine is running locally on Windows or remotely
#on linux (in which case, read in arguments passed from bash)

print(sys.argv)

if os.name == 'nt':    
    features               = ['Convenience Store']
    # crime                  = 'MURDER/NON-NEG/MANSLTR-GUN'
    iterations             = 10
    distancerange          = 1000
    buffer                 = 300
    ses_lowerbound         = 0.0
    ses_upperbound         = 5.0
    breakpoint_sensitivity = 5  
    save                   = True
    plots                  = True
    
    path = ''
    city_sfx = "pgh"
    id_flag = 1
    
else:
    features               = [sys.argv[1]]
    # crime                  = sys.argv[2]
    iterations             = int(sys.argv[2])
    distancerange          = int(sys.argv[3])
    buffer                 = int(sys.argv[4])
    ses_lowerbound         = float(sys.argv[5])
    ses_upperbound         = float(sys.argv[6])
    breakpoint_sensitivity = int(sys.argv[7])
    save                   = sys.argv[8]
    plots                  = sys.argv[9]
    path                   = sys.argv[10]
    city_sfx               = sys.argv[11]
    id_flag                = sys.argv[12]
    

# Set directory
os.chdir(path)

print(features)
    
# Set up the multiprocessing pool. Use slightly less than all the cores
# (so that I can read through stackexchange while the pool runs . . )
cores = mp.cpu_count() -2
print("Cores count is: {}".format(cores))
# p     = Pool(cores)

# Set up the logger settings
lg.basicConfig(filename = "firearm_sim.log", 
               format   = '%(asctime)s %(levelname)s: \n\r%(message)s\n',
               datefmt  ='%Y-%m-%d %H:%M:%S',
               level    = lg.DEBUG,
               filemode = 'w')

lg.debug("All packages loaded & options initialized. \n")

lg.debug("Code is running for the following features: {} \n".format(features))


# ###########################################
# # 2b. Real Data - Load the Street Network #
# ###########################################
G = nx.DiGraph(nx.read_gpickle(city_sfx + '_network_graph_v5.gpickle'))
G = G.to_undirected()

def nodes_to_df(g):

    nx_attributes = list()

    #Build a dataframe holding all of the node attributes
    for n in g.nodes(data = False):
    
       # Try/except is necessary here because a large fraction of nodes are intersections without 
       # any attributes; conversely, if a node isn't in the nx_attributes dataset, that indicates it's purely an intersection
       try:
           node_attributes = g.nodes[n]
           nx_attributes.append(node_attributes)
       except KeyError:
           pass  
       
    n_n_df = pd.DataFrame(nx_attributes)

    n_n_df['NodeID'] = pd.Series([n for n in g.nodes()])

    return n_n_df


def edges_to_df (g):
    
    nx_attributes = list()

    #Build a dataframe holding all of the node attributes
    for u, v in g.edges(data = False):
        
       #Try/except is necessary here because a large fraction of nodes are intersections without 
       #any attributes; conversely, if a node isn't in the nx_attributes dataset, that indicates it's purely an intersection
       try:
           edge_attributes = G.get_edge_data(u, v)
           nx_attributes.append(edge_attributes)
       except KeyError:
           pass  
       
    n_e_df = pd.DataFrame(nx_attributes)

    n_e_df['start_node'] = pd.Series([u for u, v in G.edges()])
    n_e_df['end_node']   = pd.Series([v for u, v in G.edges()])

    return n_e_df 


network_nodes = nodes_to_df(G)
network_edges = edges_to_df(G)

#Get a list of the unique nodes
nodes = np.unique(network_nodes['NodeID']).tolist()


#Pull the shot_nodes out from the network_nodes dataframe
shot_nodes    = network_nodes.loc[network_nodes['category'] == 'Gunshot']

lg.debug("Graph loaded and network & shot attributes dataframes created & saved. \n")

def percentile(n):
    def percentile_(x):
        return np.percentile(x, n)
    percentile_.__name__ = 'percentile_%s' % n
    return percentile_

def add_simulated_graph_features(g, e_data, index, counter):

    #Load all the information we'll need to add a new node, interpolate
    #edges from the pre-existing nodes to the new node
    new_node_id = max(g.nodes)  + counter

    start_id = e_data.loc[index, "start_node"]
    end_id   = e_data.loc[index, "end_node"]
    w        = e_data.loc[index, "weight"]

    start_x = g.nodes[start_id]['x']
    start_y = g.nodes[start_id]['y']
    
    end_x   = g.nodes[end_id]['x']
    end_y   = g.nodes[end_id]['y']
        
    edge_percent  = rng.uniform(0, 1)
    start_to_node = round(edge_percent*w, 2)
    node_to_end   = round(w - start_to_node, 2)
    
    #If points are parallel to eachother in x or y, then calculate the distance
    #as the edge_percentage difference between them. Otherwise, we'll need to
    #calculate the slope of the line to determine the x & y of the new node.
    
    if start_x != end_x:
        slope = (end_y - start_y)/(end_x - start_x)
        b = start_y - (slope * start_x)
    
        y_sim = slope * (start_x + edge_percent * (end_x - start_x))+ b
        
        if start_y != end_y:
            x_sim = (y_sim - (start_y - slope* start_x))/ slope
        else:
            x_sim = start_x + round(edge_percent * (end_x - start_x), 2)
    else:
        y_sim = start_y + round(edge_percent * (end_y - start_y), 2)
        x_sim = start_x
    
    new_node       = (new_node_id, {"NodeID":new_node_id, "category":"sim_shot", "x":x_sim, "y":y_sim})
    
    new_edge_start = (start_id, new_node_id, {"weight":start_to_node})
    new_edge_end   = (new_node_id, end_id, {"weight":node_to_end})
    edge_remove    = (start_id, end_id)
    
    return [new_node, new_edge_start, new_edge_end, edge_remove]

def simulate_random_shots(graph_observed):
    graph_simulated = graph_observed.copy()
    
    #Pull out the data on edge_ids & weights from the network graph

    edge_data = network_edges[(network_edges.core_city == 1)]
    edge_data["weight_percent"] = edge_data["weight"]/edge_data["weight"].sum()
    
    #Create random draws of edges from the network. NOTE: The below returns the indices of the dataframe
    #holding an edge list, not the edge ids themselves.
    draws   = rng.choices(list(edge_data.index), weights = list(edge_data.weight_percent), k = shot_nodes.shape[0])
    
    #For each draw, add a new simulated shot to the edge corresponding to the draw id
    new_graph_features = [add_simulated_graph_features(graph_simulated, edge_data, d, c) for d, c in zip(draws, range(len(draws)))]
    
    #Pull out the results from the new graph features and add them to the simulated graph. 
    collected_new_nodes      = [x[0] for x in new_graph_features]
    collected_new_edge_start = [x[1] for x in new_graph_features]
    collected_new_edge_end   = [x[2] for x in new_graph_features]
    collected_edge_remove    = [x[3] for x in new_graph_features]
    
    graph_simulated.add_nodes_from(collected_new_nodes)
    graph_simulated.add_edges_from(collected_new_edge_start)
    graph_simulated.add_edges_from(collected_new_edge_end)
    graph_simulated.remove_edges_from(collected_edge_remove)

    return(graph_simulated)

def distance_calculator (g, f_name, feature_node_id, shot_node_id, dist_range, buff, n_n_df):
    """Determines the network distance between a 
    feature observation and a shot observation."""
    
    feature       = n_n_df[n_n_df['NodeID'] == feature_node_id]
    feature_coord = (feature.y.values[0], feature.x.values[0])
    
    shot          = n_n_df[n_n_df['NodeID'] == shot_node_id]
    shot_coord    = (shot.y.values[0], shot.x.values[0])
    
    #First, make sure the geodesic distance is reasonably close to our maximum range.
    #We do this to ensure we're not running the axstar function for irrelevant distances.
    #This aids in speeding up the calculation time.
    
    if gp.geodesic(feature_coord, shot_coord).feet < dist_range + buff:
        dist_between = nx.astar_path_length(g, source = feature_node_id, target = shot_node_id, weight = 'weight')
    else:
        dist_between = "Outside buffered range"
    
    return {'feature_name':f_name, 'feature_id': feature_node_id, 'shot_id': shot_node_id, 'distance':dist_between}

def shot_counter (f_name, d, dist_mat): 
    
    # "Calculates the number of shots within a given distance from a feature"    
    dist_mat = dist_mat[dist_mat['distance'] != "Outside buffered range"]

    
    #Make sure not to double-count shots, by only counting the unique shot_ids
    shot_counts  = dist_mat[dist_mat['distance'] <= d].shot_id.unique().size
    shot_density = shot_counts/d
    
    return {'feature_name': f_name, 'distance': d, 'shot_counts':shot_counts, 'shot_density':shot_density}

def cross_k (g, g_id, f_name, f_ids, s_ids, dist, s_c_mat):
    
    network_size = g.size(weight='weight')
    print("network size is {}".format(network_size))
    
    shot_count = s_c_mat[s_c_mat['distance'] == dist].shot_counts.values[0]
    
    number_features = f_ids.size
    number_shots    = s_ids.size
    
    cross_k = (network_size * shot_count)/(number_features * number_shots)
    
    return {'sim_graph_id':g_id, 'feature_name':f_name, 'distance':dist, 'cross_k':cross_k}

def estimate_cross_k (sim_graph, feature_name, g_id):
    
    """Runs all of the earlier created functions (distance calculator, shot counter, 
    cross-k, piecewise), in the appropriate order."""
    
    lg.debug("Starting cross-k calculations for graph sim {}, {} \n".format(g_id, feature_name))
    
    n_n = nodes_to_df(sim_graph)
    
    #Create list of feature node ids and shot ids
    print("Feature name is {}".format(feature_name))

    feature_ids     = n_n.loc[n_n['category'] == feature_name, 'NodeID']
    shot_ids        = n_n.loc[n_n['category'] == 'sim_shot', 'NodeID']

    
    #Using the lists of features and shots, calculate the distance between the two
    distance_matrix = pd.DataFrame([distance_calculator(sim_graph, feature_name, f, s, distancerange, buffer, n_n) for f in feature_ids for s in shot_ids])
    
    #Use the calculated distances to determine the number of shots within a given range
    shot_count_matrix = pd.DataFrame([shot_counter(feature_name, dist, distance_matrix) for dist in range(5, distancerange + 5, 5)])
    
    #Calculate cross-k
    cross_k_matrix =  pd.DataFrame([cross_k(sim_graph, g_id, feature_name, feature_ids, shot_ids, dist, shot_count_matrix) for dist in range(5, distancerange + 5, 5)])
    
    lg.debug("Success! Graph sim {}, {} is now finished \n".format(g_id, feature_name))
    
    return cross_k_matrix

if sim_env==TRUE:
#Produce graphs with random simulated shots for each iteration.
    lg.debug("Building simulated shot graphs \n")

    simulated_graphs = [simulate_random_shots(G) for _ in range(iterations)]

    for ix, g in enumerate(simulated_graphs):
        print(ix)
        name = city_sfx + "_sim_graph_" + str(ix+190) + ".gpickle"
        nx.write_gpickle(g, name)

        graph_list = list(range(int(iterations)*int(id_flag)-int(iterations),int(iterations)*int(id_flag)))
        simulated_graphs = [nx.DiGraph(nx.read_gpickle(city_sfx + "_sim_graph_" + str(i) + ".gpickle")) for i in graph_list]

else: 
    #%%
    #For each graph & feature, calculate cross-k
    lg.debug("Success! Now calculating cross-k for each simulated graph and feature \n")
    cross_k_sim_results = [estimate_cross_k(g, f, i) for f in features for g, i in zip(simulated_graphs, range(len(simulated_graphs)))]

    lg.debug("Success! Now plotting & saving the results \n")

    cross_k_sim_results = pd.concat(cross_k_sim_results)

    save_name = features[0]

    if save_name == "University/College":
        save_name = "UniCollege"

    if save:
        cross_k_sim_results.to_csv(city_sfx + '_' + save_name + '_' + str(id_flag) + "_cross_k_simulated_results.csv", index = False)

    lg.debug("Full results saved \n")

        



