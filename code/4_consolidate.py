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

print("Start")
print(sys.argv)

ses_suffix = '_highses_'

# pgh transit station high
# pgh convenience store high/low
# nola transit station low
# nola gas stations high/low
# det transit station high/low
# det liqlics high/low
# la transit stations high/low
# la convenience store low


if os.name == 'nt':    
    features               = ['Convenience store or supermarket']
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
    city_sfx = "la"
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


def percentile(n):
    def percentile_(x):
        return np.percentile(x, n)
    percentile_.__name__ = 'percentile_%s' % n
    return percentile_


features_nym = features[0]

if features[0] == "University/College":
    features_nym = "UniCollege"

#%%
cross_k_sim_hold = pd.read_csv(city_sfx + '_' + str(features_nym) + ses_suffix + str(1) + "_cross_k_simulated_results.csv")
# cross_k_sim_hold = pd.read_csv(city_sfx + '_' + str(features_nym) + '_' + str(1) + "_cross_k_simulated_results.csv")
# Remember that we ran 5 iterations at a time, for all cities except LA
if city_sfx == "la":
    end = 201
else:
    end = 41

for x in range(2, end):
    df =  pd.read_csv(city_sfx + '_' + str(features_nym) + ses_suffix + str(x) + "_cross_k_simulated_results.csv")
    # df =  pd.read_csv(city_sfx + '_' + str(features_nym) + '_' + str(x) + "_cross_k_simulated_results.csv")

    cross_k_sim_hold = cross_k_sim_hold.append(df)

cross_k_sim_results = cross_k_sim_hold

#Transform the cross-k results into a pivoted dataset
#For use graphing cross-k results against observed cross-k.

#The line of code below is very dense but briefly:
#We take the cross-k results, group those results by distance and feature
cross_k_simulated = cross_k_sim_results.set_index(["distance", "feature_name"]).groupby(["distance", "feature_name"])["cross_k"].agg(
                                                                                        ["min", "max","mean", "median", percentile(2.5), percentile(97.5)]).rename(columns = {'min':'cross_k_min',
                                                                                                  'max' : 'cross_k_max',
                                                                                                  'mean' :'cross_k_mean' ,
                                                                                                  'median' : 'cross_k_median',
                                                                                                  'percentile_2.5' : 'cross_k_lower' ,
                                                                                                  'percentile_97.5': 'cross_k_upper'}).reset_index()

if save:
    cross_k_simulated.to_csv(city_sfx + ses_suffix + str(features_nym) + "_cross_k_simulated.csv", index = False)
    # cross_k_simulated.to_csv(city_sfx + str(features_nym) + "_cross_k_simulated.csv", index = False

lg.debug("Summary results saved \n")

#%%
# cross_k_observed = pd.read_csv(city_sfx + "_cross_k_observed.csv")
cross_k_observed = pd.read_csv(city_sfx+ ses_suffix + "convenience_cross_k_observed.csv")

cross_k_compiled = cross_k_observed.merge(cross_k_simulated, how = 'inner', on = ["feature_name", "distance"])

#### get analysis, determine whether attractor, neutral or repellant

conditions = [(cross_k_compiled['cross_k_observed'] >= cross_k_compiled['cross_k_max']) ,
              (cross_k_compiled['cross_k_observed'] > cross_k_compiled['cross_k_min']) & ((cross_k_compiled['cross_k_observed'] < cross_k_compiled['cross_k_max'])),
              (cross_k_compiled['cross_k_observed'] <= cross_k_compiled['cross_k_min']) ]


choices = ['Attractor', 'Neutral', 'Repellant']

cross_k_compiled['FeatureType'] = np.select(conditions, choices, default= 'NA')

# cross_k_compiled.to_csv(city_sfx + '_' + str(features_nym) + ses_suffix + "cross_k_observed_v_simulated.csv", index = False)
cross_k_compiled.to_csv(city_sfx + ses_suffix + str(features_nym) + "_cross_k_observed_v_simulated.csv", index = False)

# changes = cross_k_compiled.groupby((cross_k_compiled['FeatureType'] != cross_k_compiled['FeatureType'].shift()).values).last()
cross_k_smoothed = cross_k_compiled.copy()

cross_k_smoothed['FeatureType'] = np.where((cross_k_smoothed['FeatureType'].shift(+1) == cross_k_smoothed['FeatureType'].shift(-1)) & 
                                          (cross_k_smoothed['FeatureType'] != cross_k_smoothed['FeatureType'].shift(-1)),
                                  cross_k_smoothed['FeatureType'].shift(-1), cross_k_smoothed['FeatureType'])

changes2 = cross_k_compiled[cross_k_compiled['FeatureType'] != cross_k_compiled['FeatureType'].shift(-1)]

print(changes2)

def cross_k_plot(f_name, c_k_mat):

    
    c_k_mat = c_k_mat[c_k_mat["feature_name"] == f_name]

    if f_name == "Fedex":
        f_name = "Shipping Company 1"

    if f_name == "UPS":
        f_name = "Shipping Company 2"

    if f_name == "LiqLics":
        f_name = "Liquor Licenses"
    
    """For a given feature, plot the cross-k results by distance"""
    plot = (ggplot(c_k_mat, aes(x = 'distance', y = 'cross_k_observed')) 
        + geom_line(size = 1) 
        + geom_line(aes(y = "cross_k_median"), alpha = 0.7, color = 'navy', size = 1)
        + geom_ribbon(aes(ymin = "cross_k_lower", ymax = "cross_k_upper"), alpha = 0.3, fill = 'navy')
        + theme_classic()
        + labs(x = "Distance from {}".format(f_name),
               y = "Cross-K value",
               title = "Cross-k observed v. simulated\n for {}".format(f_name))
        + theme(legend_position = "bottom"))
    
    return plot

cross_k_plots = [cross_k_plot(x, cross_k_compiled) for x in features]
# save_as_pdf_pages([x for x in cross_k_plots], filename = city_sfx + '_' + str(features_nym) + '_'+ "cross_k_observed_v_simulated.pdf", filepath = path)

save_as_pdf_pages([x for x in cross_k_plots], filename = city_sfx + ses_suffix + str(features_nym) + '_'+ "cross_k_observed_v_simulated.pdf", filepath = path)

#%%
#Plot Observed and Simulated Cross K Functions
# K = pd.DataFrame(pd.read_csv(city_sfx + '_' + "cross_k_observed.csv"), columns=['feature_name','distance','cross_k_observed'])
# Ksimdf = pd.DataFrame(pd.read_csv(city_sfx  + '_'+ str(features_nym) + "_cross_k_simulated.csv"), columns=['feature_name','distance','cross_k_mean'])

# K = pd.DataFrame(pd.read_csv(city_sfx + ses_suffix + "cross_k_observed.csv"), columns=['feature_name','distance','cross_k_observed'])
K = pd.DataFrame(pd.read_csv(city_sfx + ses_suffix + "convenience_cross_k_observed.csv"), columns=['feature_name','distance','cross_k_observed'])

Ksimdf = pd.DataFrame(pd.read_csv(city_sfx  + ses_suffix + str(features_nym) + "_cross_k_simulated.csv"), columns=['feature_name','distance','cross_k_mean'])

for f in features:
    Kdf = K.loc[K['feature_name'] == f, :]

    if Kdf.empty:
        print('Cross K empty - No CrossK Observed, There may not be any instances of ' + str(f))
        continue
    else:
        Ksimdf = Ksimdf.loc[Ksimdf['feature_name'] == f, :]

        Ksim_mean = Ksimdf.set_index('distance').groupby(level=['distance'])['cross_k_mean'].mean()
        Ksim_mean = Ksim_mean.reset_index()

        stat = stats.ks_2samp(Kdf['cross_k_observed'], Ksim_mean['cross_k_mean'])
        # with open(city_sfx + '_' + str(features_nym) + "_ks_stat.txt", 'a') as fh:
        with open(city_sfx + ses_suffix + str(features_nym) + "_ks_stat.txt", 'a') as fh:

            fh.write(str(stat))
        print(stat)


