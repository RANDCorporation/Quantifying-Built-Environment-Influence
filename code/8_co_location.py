#! /usr/bin/env python

# Import Python libraries
import pandas as pd 
import networkx as nx  
import ruptures as rpt
import geopy.distance as gp
import os
import sys

#Plotting package, emulating ggplot
from plotnine import ggplot, aes, theme_classic, labs, stat_smooth, geom_point, save_as_pdf_pages, stat_summary
import statsmodels.formula.api as smf

#Import the logger, to aid with debugging
import logging as lg

#Set up initial options, parameters, and loggers
test  = False
plots = True
save  = True

print("Running now")

if test:
    features = ['Public health departments']

distancerange = 1000
buffer = 300

breakpoint_sensitivity = 7.5

if os.name == 'nt': 
    city_sfx = 'pgh'
    path = ''
    
else:
    city_sfx = sys.argv[1]
    path = ''
    
os.chdir(path)

#Set up the logger settings
lg.basicConfig(filename = city_sfx + "_log_messages.log", 
               format = '%(asctime)s %(levelname)s: \n\r%(message)s\n',
               datefmt='%Y-%m-%d %H:%M:%S',
               level = lg.DEBUG,
               filemode = 'w')

lg.debug("All packages loaded & model parameters initialized")

if test:
    lg.debug("Test == TRUE; Only running models for the following features: %s", features)

#%%

G = nx.DiGraph(nx.read_gpickle(city_sfx + '_network_graph_v5.gpickle'))
G = G.to_undirected()

lg.debug("Network graph for Los Angeles read successfully" )

def convert_network_nodes_to_df (g):
    
    nx_attributes = list()
    n_nodes = list()

    #Build a dataframe holding all of the node attributes
    for n in g.nodes(data = False):
       #Try/except is necessary here because a large fraction of nodes are intersections without 
       #any attributes; conversely, if a node isn't in the nx_attributes dataset, that indicates it's purely an intersection
       try:
           node_attributes = g.nodes[n]
           nx_attributes.append(node_attributes)
           n_nodes.append(n)
       except KeyError:
           pass  
       
    n_n_df = pd.DataFrame(nx_attributes)
    n_n_df['NodeID'] = pd.Series(n_nodes)

    return n_n_df

network_nodes = convert_network_nodes_to_df(G)

lg.debug("Network node dataframes have been produced")

#For each feature & distance, calculate the number of shots within that distance,
#to a given feature 

lg.debug("Now estimating shot densities by feature")

#Transform all the weights in the network into feet, rather than meters.
for u, v, d in G.edges(data = True):
    d['weight'] = d['weight']*3.28084
    
#Get a list of all the features in the network. Note: This will be overriden, if "test == True"
# feature_list = network_nodes[network_nodes['category'] != "Gunshot"].category.unique().tolist()
feature_list = network_nodes[network_nodes['category'] != "Gunshot"].category.unique().tolist()

#Nans are being introduced to the feature list, due to an issue with the creation
#of the network_nodes dataframe. This will need to be dealt with later but for now,
#a temporary fix so I can proceed:

feature_list = [x for x in feature_list if x == x]
print(feature_list)

#Temporarily, set feature_list to a subset of all features, for debuggin purposes.
#This should be removed or commented out for a run using all features
if test:
    feature_list = features

#%%
#Set up all our functions, needed to calculate cross-k & the piecewise regression

def distance_calculator (f_name1, f_name2, feature1_node_id, feature2_node_id, dist_range, buff):
    """Determines the network distance between a 
    feature observation and a shot observation."""

    dist_between = nx.astar_path_length(G, source = feature1_node_id, target = feature2_node_id, weight = 'weight')

    # if gp.geodesic(feature_coord, shot_coord).feet < dist_range + buff:

    # else:
    #     dist_between = "Outside buffered range"

    return {'feature_name1':f_name1, 'feature_name2': f_name2, 'feature1_id': feature1_node_id, 'feature2_id': feature2_node_id, 'distance':dist_between}

def estimate_cross_k_and_piecewise (feature_name1, feature_name2):

    """Runs all of the earlier created functions (distance calculator, shot counter, 
    cross-k, piecewise), in the appropriate order."""
    lg.debug("Starting cross-k calculations & piecewise regressions for {}".format(feature_name1))

    #Create list of feature node ids and shot ids
    feature_ids1     = network_nodes.loc[network_nodes['category'] == feature_name1, 'NodeID']
    feature_ids2     = network_nodes.loc[network_nodes['category'] == feature_name2, 'NodeID']
    # feature_ids2     = network_nodes.loc[network_nodes['category'].isin(["Restaurants","Alcohol outlet"]) , 'NodeID']

    #Count instances of feature
    # n_feature = len(feature_ids)

    #Using the lists of features and shots, calculate the distance between the two
    distance_matrix = pd.DataFrame([distance_calculator(feature_name1, feature_name2, f1, f2, distancerange, buffer) for f1 in feature_ids1 for f2 in feature_ids2])

    lg.debug("Success! {} is now finished".format(feature_name1))

    return [distance_matrix]

#%%
#Below, this is the meat of the action. This runs the "estimate_shot_density" function, which runs all the subsidiary functions.
# 'Lodging' 'Alcohol outlet' 'Restaurants'
results = [estimate_cross_k_and_piecewise(feature_name1 = "Fast Food", feature_name2 = "Bank" )]

collected_distance_matrices   = pd.concat([x[0] for x in results], axis = 0)

lg.debug("All features finished for cross-k and piecewise regression. Results compiled successfully!")

if save:
    collected_distance_matrices.to_csv(city_sfx + "_distances_observed_fastfood_bank.csv", index = False)
    # collected_shot_count_matrices.to_csv(city_sfx + "_shot_counts_observed.csv", index = False)
    # collected_cross_k_matrices.to_csv(city_sfx + "_cross_k_observed.csv", index = False)

    lg.debug("All datasets have been saved.")

lg.debug("All finished!")
