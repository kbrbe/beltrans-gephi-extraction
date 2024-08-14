import pandas as pd

# -----------------------------------------------------------------------------
def main():

  # Please provide the name of the input file and output files
  inputFile = 'corpus-data.xlsx'
  edgeListFilename = 'edge-list.csv'
  nodeListFilename = 'node-list.csv'

  # all beltrans genre prefixes "81|83|84|85|86|900|92|93|95|96|97"

  # Select which genre filter should be used (comment the others with a leading #)
  #genrePrefixes = "84|900|92|93|95|96|97" # history
  #genrePrefixes = "85" # Comics
  #genrePrefixes = "81" # Poetry
  genrePrefixes = "86" # juvenile literature
  #genrePrefixes = "83|84" # novels

  minYear = pd.to_numeric('1970')
  maxYear = pd.to_numeric('2020')

  # if set to True source/target publishers will be replaced by their respective main publisher
  # otherwise set to False
  considerImprintRelation = True

  # Identifiers of imprints that should not be replaced with their main publisher (in case there is any specified)
  # This is a list, when adding new entries, please put a comma after the string and before the comment, e.g. before "# pastel"
  imprintMappingExceptions = [
    '9e29c2cd-b380-49e3-82d6-141914ff35c0' # pastel
  ]

  # use names instead of identifiers for nodes and edges (if there are no duplicates)
  # a warning is printed when duplicate names are encountered
  namesInsteadOfIdentifiers = False

  # Begin of the code
  #
  print(f'read translations from Excel...')
  dfTranslations = pd.read_excel(inputFile, sheet_name='translations')

  print(f'read organization list from Excel ...')
  dfOrgs = pd.read_excel(inputFile, sheet_name='all orgs')

  # store the mapping in a separate data structure so we can reuse it
  imprintMapping = dfOrgs[['contributorID', 'isImprintFrom']].copy()

  # create edge list with information from the nodes (needed for correct mapping of imprints)
  # we first have to create edges, because based on them we have to filter nodes afterwards and add aggregated numbers
  edgeDf = createEdgeList(dfTranslations, genrePrefixes, minYear, maxYear, considerImprintRelation, imprintMapping, imprintMappingExceptions)

  # no imprintMapping needed for the following function, because the mapping information is already in dfOrgs
  nodesDf = createNodeList(dfOrgs, edgeDf, considerImprintRelation, imprintMappingExceptions)

  if namesInsteadOfIdentifiers:
    # https://github.com/kbrbe/beltrans-gephi-extraction/issues/1
    replaceIdentifiersIfPossible(edgeDf, nodesDf)

  edgeDf.to_csv(edgeListFilename, index=False)
  nodesDf.to_csv(nodeListFilename, index=False)

# -----------------------------------------------------------------------------
def replaceIdentifiersIfPossible(edgeDf, nodesDf):

  # replace identifiers with names https://github.com/kbrbe/beltrans-gephi-extraction/issues/1
  # but only if names are unique in the current data
  numberDuplicateNames = nodesDf['Label'].duplicated().sum()
  if numberDuplicateNames > 0:
    print(f'node identifiers NOT replaced with names, because names were found not to be unique')
    print(f'Number of duplicate names: {numberDuplicateNames}')
    names = nodesDf['Label']
    print(relevantNodesDf[names.isin(names[names.duplicated()])])
  else:
    # replace Id with Label for edges
    nodeMapping = nodesDf[['Id', 'Label']]
    nodeMappingDict = nodeMapping.set_index('Id')['Label'].to_dict()

    edgeDf['Source'] = edgeDf['Source'].map(nodeMappingDict)
    edgeDf['Target'] = edgeDf['Target'].map(nodeMappingDict)

    # replace Id with Label for nodes
    nodesDf['Id'] = nodesDf['Label']



# -----------------------------------------------------------------------------
def createNodeList(dfOrgs, edgeDf, considerImprintRelation, imprintMappingExceptions):

  columnsToKeep = ['contributorID', 'name', 'country']

  # only select nodes that exist in the edges https://github.com/kbrbe/beltrans-gephi-extraction/issues/3
  # additionally only keep the columns we are interested in
  # We have to use the operator '|' instead of 'or', because the latter is for boolean operations in Pandas
  relevantNodesDf = dfOrgs.loc[ (dfOrgs['contributorID'].isin(edgeDf['Source'])) | (dfOrgs['contributorID'].isin(edgeDf['Target'])), columnsToKeep]


  # default Gephi column names for node ID and label https://github.com/kbrbe/beltrans-gephi-extraction/issues/5
  relevantNodesDf.rename(columns={'contributorID': 'Id', 'name': 'Label'}, inplace=True)

  # empty countries instead of NaN
  relevantNodesDf = relevantNodesDf.fillna('')

  # add counts of edge attributes for nodes https://github.com/kbrbe/beltrans-gephi-extraction/issues/4
  # first count
  flowCountsSource = countTranslationFlow(edgeDf, 'Source')
  flowCountsTarget = countTranslationFlow(edgeDf, 'Target')

  # then merge the counts to the nodes dataframe and make sure the numbers are integer
  relevantNodesDf = relevantNodesDf.merge(flowCountsSource, left_on='Id', right_index=True, how='left').fillna(0)
  relevantNodesDf = relevantNodesDf.merge(flowCountsTarget, left_on='Id', right_index=True, how='left').fillna(0)
  columnsToConvert = [col for col in relevantNodesDf.columns if col.startswith(('Source', 'Target'))]
  relevantNodesDf[columnsToConvert] = relevantNodesDf[columnsToConvert].astype(int)

  relevantNodesDf[['mostCommonPlaceOfPublicationTarget', 'mostCommonCountryOfPublicationTarget', 'placesOfPublicationTarget', 'countriesOfPublicationTarget']] = relevantNodesDf.apply(countPlacesOfPublication, edgeDf=edgeDf, locationColumns=['targetPlaceOfPublication', 'targetCountryOfPublication'], locationOf='Target', axis=1)
  relevantNodesDf[['mostCommonPlaceOfPublicationSource', 'mostCommonCountryOfPublicationSource', 'placesOfPublicationSource', 'countriesOfPublicationSource']] = relevantNodesDf.apply(countPlacesOfPublication, edgeDf=edgeDf, locationColumns=['sourcePlaceOfPublication', 'sourceCountryOfPublication'], locationOf='Source', axis=1)

  return relevantNodesDf

  # for now the country of the publisher record (not always filled in)
  #
  # in case we want country information from the translation list,
  # dfTranslations should be given as a parameter,
  # then we would have to select all countries of each dfOrgs['contributorID'] in an exploded version of dfTranslations
  # and add it
  # is this what we want? Like this we might get wrong country information, especially for translations with multiple publishers and thus publishing places
    
# -----------------------------------------------------------------------------
def countPlacesOfPublication(row, edgeDf, locationColumns, locationOf):
  """This function returns a series with 4 values. It is used to populate 4 columns in the output dataframe."""

  rowID = row['Id']

  #
  # get place and country edge values for current node (publisher) in the edges dataframe
  # only take location information from where the current node is the TARGET publisher
  #
  locationInfoDf = edgeDf.loc[ (edgeDf[locationOf] == rowID), locationColumns]

  if locationInfoDf.empty:
    return pd.Series(['','','',''])

  # We don't assume that the column values are sorted, thus sort separated string, for example "Paris;Brussels" => "Brussels;Paris"
  for col in locationColumns:
    locationInfoDf[col] = locationInfoDf[col].apply(lambda val: ';'.join(sorted(val.split(';'))))

  # We need the combination of values, not the exploded components (https://github.com/kbrbe/beltrans-gephi-extraction/issues/7#issuecomment-2285676618)
  # For example "Brussels;Paris" and not "Brussels" and "Paris"
  places = locationInfoDf[locationColumns[0]]
  countries = locationInfoDf[locationColumns[1]]

  # Count occurrences of combinations (https://github.com/kbrbe/beltrans-gephi-extraction/issues/7#issuecomment-2285719024)
  #
  placeCountsSeries = locationInfoDf[locationColumns[0]].value_counts()
  placeCountsString = ','.join([f'{place} ({count})' for place, count in placeCountsSeries.items()])
  countryCountsSeries = locationInfoDf[locationColumns[1]].value_counts()
  countryCountsString = ','.join([f'{country} ({count})' for country, count in countryCountsSeries.items()])

  # mode wil return the most frequent element in the series (https://stackoverflow.com/questions/48590268)
  retVal = [
    places.mode().tolist()[0], 
    countries.mode().tolist()[0], 
    placeCountsString, 
    countryCountsString
  ]

  return pd.Series(retVal)

# -----------------------------------------------------------------------------
def countTranslationFlow(edgeDf, columnName):

  flowCounts = edgeDf.groupby([columnName, 'translationFlow']).size().unstack(fill_value=0).astype(int)
  flowCounts = flowCounts.reindex(columns=['FR-NL', 'NL-FR'], fill_value=0).astype(int)
  flowCounts.columns = [f'{columnName}_FR-NL', f'{columnName}_NL-FR']
  return flowCounts.astype(int)
  
# -----------------------------------------------------------------------------
def createEdgeList(dfTranslations, genrePrefixes, minYear, maxYear, considerImprintRelation, imprintMapping, imprintMappingExceptions):


  sourceTargetColumns = ['sourcePublisherIdentifiers', 'targetPublisherIdentifiers']
  genreColumn = 'targetThesaurusBB'
  additionalInfoColumns = ['targetYearOfPublication', 'sourceLanguage', 'targetLanguage', 
                           'sourcePlaceOfPublication', 'sourceCountryOfPublication', 'targetPlaceOfPublication', 'targetCountryOfPublication']


  # We want one row = one source-target relation
  # thus first make an array based on the string lists and then explode
  for col in sourceTargetColumns: 
    dfTranslations[col] = dfTranslations[col].str.split(';')

  edgeDfExploded = dfTranslations.explode(sourceTargetColumns[0]).explode(sourceTargetColumns[1]).reset_index().copy()
 
  # We also only want a subset of the columns
  edgeDfExploded = edgeDfExploded.fillna('')
  edgeDf = edgeDfExploded.loc[edgeDfExploded[genreColumn].str.contains(genrePrefixes), sourceTargetColumns + additionalInfoColumns]

  # extract identifiers
  edgeDf['sourceID'] = edgeDf[sourceTargetColumns[0]].str.extract(r'.*\((.*)\).*')
  edgeDf['targetID'] = edgeDf[sourceTargetColumns[1]].str.extract(r'.*\((.*)\).*')

  # replace source and target identifiers with main publisher in case we should take the imprint relation into account
  if considerImprintRelation:
    mergedDf = pd.merge(edgeDf, imprintMapping, left_on='sourceID', right_on='contributorID', how='left')
    mergedDf['sourceID'] = mergedDf.apply(replaceImprint, axis=1, imprintIDColumn='sourceID', mainIDColumn='isImprintFrom', replaceColumn='isImprintFrom', keepColumn='sourceID', exceptions=imprintMappingExceptions)
    mergedDf.drop(['contributorID', 'isImprintFrom'], axis=1, inplace=True)

    mergedDf = pd.merge(mergedDf, imprintMapping, left_on='targetID', right_on='contributorID', how='left')
    mergedDf['targetID'] = mergedDf.apply(replaceImprint, axis=1, imprintIDColumn='targetID', mainIDColumn='isImprintFrom', replaceColumn='isImprintFrom', keepColumn='targetID', exceptions=imprintMappingExceptions)
    mergedDf.drop(['contributorID', 'isImprintFrom'], axis=1, inplace=True)

    edgeDf = mergedDf.copy()

  # finally only selecting a specific date range
  edgeDf['targetYearOfPublication'] = pd.to_numeric(edgeDf['targetYearOfPublication'], errors='coerce', downcast='integer')
  edgeDf = edgeDf.loc[(edgeDf['targetYearOfPublication'].notna()) & (edgeDf['targetYearOfPublication'] >= minYear) & (edgeDf['targetYearOfPublication'] <= maxYear)]
  

  edgeDf = edgeDf.fillna('')
  edgeDf['targetYearOfPublication'] = edgeDf['targetYearOfPublication'].astype(int)

  # Ensure we only write "real" edges to the output: edges with target AND source
  outputEdgeDf = edgeDf.loc[(edgeDf['sourceID'] != '') & (edgeDf['targetID'] != ''),['sourceID','targetID'] + additionalInfoColumns]

  # add edge list attribute for translation flow https://github.com/kbrbe/beltrans-gephi-extraction/issues/2
  outputEdgeDf['translationFlow'] = outputEdgeDf.apply(determineTranslationFlow, axis=1)
  outputEdgeDf.drop(columns=['sourceLanguage', 'targetLanguage'], inplace=True)

  # default Gephi column names for source and target https://github.com/kbrbe/beltrans-gephi-extraction/issues/5
  outputEdgeDf.rename(columns={'sourceID': 'Source', 'targetID': 'Target'}, inplace=True)
  outputEdgeDf['Type'] = 'directed'

  return outputEdgeDf


# -----------------------------------------------------------------------------
def determineTranslationFlow(row):

  if 'French' in row['sourceLanguage'] and 'Dutch' in row['targetLanguage']:
    return 'FR-NL'
  elif 'Dutch' in row['sourceLanguage'] and 'French' in row['targetLanguage']:
    return 'NL-FR'
  else:
    return f'Unknown: {row["sourceLanguage"]} - {row["targetLanguage"]}'

# -----------------------------------------------------------------------------
def replaceImprint(row, imprintIDColumn, mainIDColumn, replaceColumn, keepColumn, exceptions):
  """This function can be called for each row, it will return the value of the replaceColumn in case there is a mainID column and in case the imprintID is not in the exception list
     otherwise the value of the keepColumn is returned.
  """

  imprintID = row[imprintIDColumn]
  mainID = row[mainIDColumn]

  if mainID in exceptions:
    # do not replace
    return row[keepColumn]
  else:
    if pd.notna(mainID):
      # replace
      return row[replaceColumn]
    else:
      # nothing to replace with
      return row[keepColumn]



# execute main function
main()
