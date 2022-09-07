# Prep SES scores

rm(list = ls())

#Load packages
library(plyr)
library(dplyr)
library(data.table)
library(mice)
library(psych)

#Read in prepped FA datasets:
la_df   <- fread("la_prepped_summary_dfa.csv")
pitt_df <- fread("pitt_prepped_summary_dfa.csv")
det_df  <- fread("det_prepped_summary_dfa.csv")
nola_df <- fread("nola_prepped_summary_dfa.csv")

ses_scores <- fread("ses_scores.csv")

# For some reason, "percent_pop_black" is missing in NOLA. So derive this:
nola_df[, pop_black := 1 - pop_white - pop_asian - pop_native_american - pop_pacific_islander]

df_collect <- list("Pittsburgh" = pitt_df, 
                   "Los Angeles" = la_df, 
                   "Detroit" = det_df,
                   "New Orleans" = nola_df)

ses_vars <- c("pop_black", "pop_female", "pop_native_american", "pop_asian",
              "pop_non_citizen", "pop_snap", "pop_pacific_islander", "avg_edu", "median_income",
              "median_rent", "unemployed_percentage", "percent_poverty_150")

#Subset to just SES variables and tracts:
for (i in 1:length(df_collect)){
  df_collect[[i]] <- df_collect[[i]][, c("census_tract", ses_vars), with = F]
}

# Create summary table, after subsetting results
df_summary <- data.table(expand.grid("location" =names(df_collect), 
                                     "variable" = ses_vars, 
                                     "group" = c(25, 50, 75)))

df_summary[, value := 0]


for (i in 1:length(df_collect)){
  for (v in ses_vars){
  
    quants <- quantile(df_collect[[i]][, (v), with = F], probs = c(0.5), na.rm = T)
    df_summary[location == names(df_collect)[i] & variable == v & group == 50, value := round(as.numeric(quants), 2)]
    
    for (s in c(25, 75)){
      
      df_subset <- join(df_collect[[i]], ses_scores, by = "census_tract")
      
      if (names(df_collect)[i] != "Pittsburgh"){
        df_subset[, ses_percentile := 100 - ses_percentile]
      }
      
      if (s == 25){
        df_subset <- df_subset[ses_percentile <= 25,]
        }else{
        df_subset <- df_subset[ses_percentile >= 75,]
      }
      
      quants <- quantile(df_subset[, (v), with = F], probs = c(0.5), na.rm = T)
      df_summary[location == names(df_collect)[i] & variable == v & group == s, value := round(as.numeric(quants), 2)]
      
    }
  }
}

# Reshape summary table wide:
df_summary <- dcast(df_summary, location + group ~ variable)

# Adjust ACS educational attainment to align with conventional estimates (e.g.
# do not count K and pre-k as years of schooling)
df_summary[, avg_edu := avg_edu - 2]

write.csv(df_summary, "ses_quartiles_across_tracts.csv", row.names = F)

# Convert all variables to z-scores. This is being done to insure variables are on 
# comparable scales for both the imputation and PCA.
for (i in 1:length(df_collect)){
  for (v in ses_vars){
    df_collect[[i]][, (v) := (get(v) - mean(get(v), na.rm = T))/sd(get(v), na.rm = T)]
  }
}

# Impute values for missing observations in ACS series

#Make sure to not use census_tract in the MICE imputations
use_preds <- matrix(data = 1,
                    nrow = length(ses_vars) + 1,
                    ncol = length(ses_vars) + 1)

rownames(use_preds) <- c("census_tract", ses_vars)
colnames(use_preds) <- c("census_tract", ses_vars)

use_preds[1, ] <- 0
use_preds[, 1] <- 0

for (i in 1:length(df_collect)){
  ses_imp <- mice(df_collect[[i]], m = 1000, method = "pmm", predictorMatrix = use_preds)
  ses_imp <- complete(ses_imp)
  
  df_collect[[i]] <- ses_imp
}

#Create PCA scores for each city, using SES variables
for (i in 1:length(df_collect)){
  setDT(df_collect[[i]])
  ses_pca <- prcomp(df_collect[[i]][, ses_vars, with = F], scale. = T)
  
  #Make sure the first loading is sufficiently larger than the next several
  print(ses_pca$sdev)
  df_collect[[i]][, ses_score := ses_pca$x[,1]]
  df_collect[[i]][, ses_percentile := round(rank(df_collect[[i]]$ses_score)/length(df_collect[[i]]$ses_score), 2)*100]
  
}

#Add on city names and save the collected dataset
cities <- names(df_collect)

for (i in 1:length(df_collect)){
  df_collect[[i]][, city := cities[i]]
  
  df_collect[[i]] <- df_collect[[i]][, .(city, census_tract, ses_percentile, ses_score, pop_black, 
                                         pop_female, pop_native_american, pop_non_citizen, pop_snap, pop_pacific_islander,
                                         avg_edu, median_income, median_rent, unemployed_percentage, percent_poverty_150)]
}

df_collect <- rbindlist(df_collect)

write.csv(df_collect, "", row.names = F)

#Crosswalk SES scores to zip codes, using HUD crosswalk weights:
#https://www.huduser.gov/portal/datasets/usps_crosswalk.html

cw_weights <- fread("hud_tract_zip_crosswalk.csv")
cw_weights <- cw_weights[, .(TRACT, ZIP, TOT_RATIO)]
setnames(cw_weights, names(cw_weights), c("census_tract", "zip_code", "weight"))

df_zip <- join(df_collect, cw_weights, by = "census_tract", type = "right")

#Use list of preferred zip codes to subset:
preferred_zips <- fread("lm_preferred_zips.csv")
preferred_zips <- unique(preferred_zips$zip_codes)

df_zip <- df_zip[zip_code %in% preferred_zips,]

#There's a bunch of census tracts where we didn't obtain ACS data. Let's get
#a list of those tracts, add them to the initial extraction, then rerun this code.
#After I've added these to a new summary file, I'll comment out the code below:

#Add on total population
df_zip <- join(df_zip, pitt_df[, .(census_tract, total_population)], by = "census_tract", type = "left")
setDT(df_zip)

#Create weights based off population of each census tract * cw weights. Then, 
#rescale weights to sum to one.
df_zip[, pop_weight := total_population*weight]
df_zip[, total_pop_weight := sum(.SD$pop_weight), by = "zip_code"]
