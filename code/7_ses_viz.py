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
import matplotlib.pyplot as plt
import seaborn as sns

import multiprocessing as mp
from multiprocessing import Pool

pd.set_option('display.max_columns', 40)

#################################################################################################
# 1. Initialize Parameters
#################################################################################################
#Determine if the machine is running locally on Windows or remotely
#on linux (in which case, read in arguments passed from bash)

# Detroit
det_features_list = ['Bank', 'Child Care Center', 'Credit union', 'Fedex', 'Fire Stations', 'Hospitals', 'Landfill', 'Law Enforcement', 
'LiqLics', 'Nursing Home', 'Pharmacy', 'Public health departments', 'RecCent', 'Schools', 'Slaughterhouses', 
'Sport Venue', 'State government', 'Transit station', 'University/College', 'UPS', 'Urgent care', 'VA', 'WIC']

# New Orleans
nola_features_list = ['Alcohol outlet', 'Bank', 'Credit union', 'Drug stores', 'Fedex', 'Fire Stations', 'Gas stations', 'Grocery Stores', 
'Hospital', 'Law Enforcement', 'Lodging', 'Nursing home', 'Pharmacy', 'Public health departments', 'Public library', 'Refrigerated warehouse', 
'Restaurants', 'School', 'Slaughterhouses', 'Sport Venue', 'Transit station', 'University/College', 'UPS', 'Urgent care', 'VA']
# nola_features_list = ['Transit station']

# Pittsburgh
pgh_features_list = ['Bank', 'Child Care Center', 'Convenience Store', 'Convenience store or supermarket', 'Credit union', 'Fast Food', 
'Fedex', 'Fire Stations', 'Hospital', 'Landfill', 'Law Enforcement', 'Library', 'Mobile Home Parks', 'Nursing Home', 'Pharmacy', 
'Playground', 'Primary care providers', 'Private school', 'Public Buildings', 'Public health departments', 'Public park', 'Public pool', 
'Public school', 'Refrigerated warehouse', 'Slaughterhouses', 'Sport court', 'Sport field', 'Sport Venue', 'State government', 
'Tobacco retailer', 'Trade school', 'Transit station', 'University/College', 'UPS', 'Urgent care', 'VA']

# Los Angeles
la_features_list = ['Convenience store or supermarket', 'Credit union', 'Fedex', 'Fire Stations', 'Hospital', 'Landfill', 'Law Enforcement', 'Mobile Home Parks', 'Museums', 'Nursing Home', 'Public health departments', 
'Slaughterhouses', 'Spectator sports', 'Sport Venue', 'State government', 'Trade school', 'Transit station', 'University/College', 'Urgent care', 'VA']

save       = True
plots      = True
smoothing  = False
pctdiff    = False
test       = False

path = ''
city_sfx = "la"


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
    # print(nx_attributes)
    n_n_df['NodeID'] = pd.Series(n_nodes)


    return n_n_df

network_nodes = convert_network_nodes_to_df(G)

# Take SES, calculate percentile
# network_nodes['fauxses'] = np.random.normal(0.5, 0.15, len(network_nodes))
# network_nodes.loc[:, 'ses_pct'] = network_nodes["fauxses"].rank(pct=True)
# print(network_nodes)

ses_scores = pd.read_csv("ses_scores.csv")
print("SES scores")

# Merge in
network_ses = network_nodes.merge(ses_scores, left_on = 'census_tract', right_on = 'census_tract')

print("Merged")
print(network_ses)

# for loop
if city_sfx=="la":
  rel_list = la_features_list
elif city_sfx=="pgh":
  rel_list = pgh_features_list
elif city_sfx == "nola":
  rel_list = nola_features_list
else:
  rel_list = det_features_list

for i in range(0,len(rel_list)):
    features = rel_list[i]

    features_nym = features

    print(features)

    if features == "University/College":
        features_nym = "UniCollege"
        rel_data = network_ses[network_ses['category'] == features]
    else:
        rel_data = network_ses[network_ses['category'] == features_nym]


    fig, axs = plt.subplots(ncols=3, sharex=True, sharey=False)

    figM, axsM = plt.subplots(ncols=3, sharex=True, sharey=True)
    plt.xticks([0,20,40,60,80,100])

    if(len(rel_data)):
        axsM[0].hist(x=rel_data['ses_percentile'],    bins=20, color= '#0504aa', alpha=0.7, rwidth=0.85)
        plt.grid(axis='y', alpha=0.75)

        sns.violinplot(x='category', y = 'ses_percentile', data=rel_data, ax=axs[0], inner= None, color= "blue")
        sns.swarmplot( x='category', y = 'ses_percentile', data=rel_data, ax=axs[0], color='white', edgecolor= "gray")
       
        low_data =  rel_data[rel_data['ses_percentile'] <= 25]
        high_data = rel_data[rel_data['ses_percentile'] >= 75]

        print("Low")
        print(len(low_data))
        print("High")
        print(len(high_data))

        if(len(low_data)):
            axsM[1].hist(x=low_data['ses_percentile'], bins=20, color= '#cc5500', alpha=0.7, rwidth=0.85)
            plt.grid(axis='y', alpha=0.75)

            sns.violinplot(x= 'category', y= 'ses_percentile', data= low_data, ax=axs[1], inner= None, color= "orange")
            sns.swarmplot(x = 'category', y= 'ses_percentile', data= low_data, ax=axs[1], color='white', edgecolor= "gray")
            
        # print(len(high_data))
        if(len(high_data)):

            axsM[2].hist(x=high_data['ses_percentile'], bins=20, color= '#228b22', alpha=0.7, rwidth=0.85)
            plt.grid(axis='y', alpha=0.75)

            sns.violinplot(x= 'category', y= 'ses_percentile', data= high_data, ax=axs[2], inner= None, color = "green")
            sns.swarmplot( x= 'category', y= 'ses_percentile', data= high_data, ax=axs[2], color='white', edgecolor= "gray")
         
        fig.tight_layout(pad=2.0)

        axs[0].set_ylabel(city_sfx)
        axs[0].set_xlabel('all ses')
        axs[1].set_xlabel('ses <= 25th pctile')
        axs[2].set_xlabel('ses >= 75th pctile')

        axsM[0].set_xlabel('all ses')
        axsM[1].set_xlabel('ses <= 25th pctile')
        axsM[2].set_xlabel('ses >= 75th pctile')

        figM.suptitle('SES Scores for ' + features_nym + ' in ' + city_sfx)

        figM.savefig(fname='' + city_sfx + "_" + features_nym + '_hist.png')
        figM.clf()

        fig.savefig(fname='' + city_sfx + "_" + features_nym + '_viz.png')
        fig.clf()


# Plot all SES scores by feature
# Histograms
g = sns.FacetGrid(network_ses, col= 'category', col_wrap = 5, height=1.5, margin_titles = True)
# bins = (0,100, 20)
g.map(plt.hist, "ses_percentile", color= "orange")
g.savefig('' + city_sfx + '_histograms.png')

allplots = sns.violinplot(x='category', y = 'ses_percentile', data= network_ses)
allp = allplots.get_figure()
allp.savefig(fname='' + city_sfx + '_fake_viz.png')

# plot = network_ses['ses_percentile'].hist(by=network_ses['category'])
# fig = plot[0][0].get_figure()


group1 = ['Alcohol outlet', 'Bank', 'Credit union', 'Drug stores', 'Fedex']
group2 = ['Fire Stations', 'Gas stations', 'Grocery Stores', 'Hospital', 'Law Enforcement']
group3 = ['Lodging', 'Nursing home', 'Pharmacy', 'Public health departments', 'Public library']
group4 = ['Refrigerated warehouse', 'Restaurants', 'School', 'Slaughterhouses', 'Sport Venue']
group5 = ['Transit station', 'University/College', 'UPS', 'Urgent care', 'VA']

# rel_data = network_ses[network_ses['category'].isin(group1)]

# Keep lowest 10th percentile of SES scores

# poorest = network_nodes.loc[network_nodes['']]

# SES scores
# Compare features in poor neighborhoods between cities. For each city, keep lowest 10 percentile of SES scores
# Histograms indicating SES percentile by feature?
