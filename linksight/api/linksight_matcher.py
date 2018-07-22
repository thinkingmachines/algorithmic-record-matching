import pandas as pd

from fuzzywuzzy import process
from itertools import dropwhile

MAX_MATCHES = 10
SCORE_CUTOFF = 80


class LinkSightMatcher:
    """Returns a dataframe containing near and exact address matches

    Attributes:
        dataset: pandas dataframe row containing the barangay, city_municipality, and province field
        dataset_index: the index of the dataset being processed
        reference: pandas dataframe containing the reference codes based on the location
        interlevels: dict containing interlevel information:
            name: interlevel name
            dataset_field_name: the dataset's column name corresponding to the interlevel
            reference_fields: list of interlevel values from the reference dataframe that are
                              considered as part of the interlevel
    """
    def __init__(self, dataset, dataset_index,
                 reference, interlevels):
        self.dataset = dataset
        self.dataset_index = dataset_index
        self.reference = reference
        self.interlevels = interlevels

    def get_matches(self):
        """Gets potential address matches based on the a dataset row

        :return: a dataframe containing all of the matches in all interlevels in the following format:
        | code | interlevel | location | province_code | city_municipality_code | score
        """
        self.dataset.fillna("", inplace=True)
        codes = []
        missing_interlevels = []
        previous_interlevel = ""
        matches = pd.DataFrame()

        for interlevel in self.interlevels:
            location = self.dataset.iloc[0][interlevel["dataset_field_name"]]

            if location == "":
                missing_interlevels.append(interlevel)
                continue

            subset = self._get_reference_subset(interlevel, codes=codes, previous_interlevel=previous_interlevel)
            partial_matches = self._get_matches(interlevel, subset)

            if len(partial_matches) == 0:
                missing_interlevels.append(interlevel)
                continue

            codes = list(partial_matches["code"])
            matches = matches.append(partial_matches)
            previous_interlevel = interlevel

        matches = self._populate_missing_interlevels(missing_interlevels, matches)
        matches["index"] = self.dataset_index
        matches.set_index("index", drop=True, inplace=True)
        return matches

    def _populate_missing_interlevels(self, missing_interlevels, matches):
        """Extracts missing higher-interlevel rows based on the matched lower-level ones. If the
        lowest level is missing, the method will add empty dataframes with higher-level interlevel
        codes populated so we can join them later

        :param missing_interlevels: list of unmatched interlevels
        :param matches: the dataframe containing the matches
        """
        for missing_interlevel in missing_interlevels:
            code_field = "{}_code".format(missing_interlevel["name"])

            if code_field not in self.reference.columns:
                partial_match = pd.DataFrame().reindex_like(matches)
                next_interlevel = self._get_next_higher_interlevel(missing_interlevel)

                field_name = "{}_code".format(next_interlevel["name"])

                partial_match[field_name] = list(matches[field_name])
                partial_match["interlevel"] = missing_interlevel["reference_fields"][0]
                partial_match.drop_duplicates([field_name], inplace=True)

                matches = matches.append(partial_match, sort=False)
                continue

            codes = set(matches[code_field])
            partial_match = self.reference[self.reference['code'].isin(codes)].copy()
            partial_match['score'] = 100
            matches = matches.append(partial_match, sort=False)

        return matches

    def _get_next_higher_interlevel(self, interlevel):
        return next(dropwhile(lambda x: x == interlevel, reversed(self.interlevels)))

    def _get_reference_subset(self, interlevel, codes=[], previous_interlevel=""):
        """Returns a subset of the reference dataset based on the current interlevel and the results
        of the previous interlevel match attempt

        :param interlevel: the dict containing info on the interlevel being processed
        :param codes: the list containing the last successfully-matched codes
        :param previous_interlevel: the dict containing info the last processed interleel
        """
        if codes:
            code_field = "{}_code".format(previous_interlevel["name"])
            subset = self.reference.loc[self.reference[code_field].isin(codes) &
                                        self.reference.interlevel.isin(interlevel["reference_fields"])]
            return subset

        return self.reference.loc[self.reference.interlevel.isin(interlevel["reference_fields"])]

    def _get_matches(self, interlevel, reference_subset):
        """Returns a dataframe containing matches found on a certain interlevel in the following format:
        | code | interlevel | location | province_code | city_municipality_code | score

        :param interlevel: the dict containing intelevel information
        :param reference_subset: the dataframe containing a subset of the reference dataframe where
                                 the matches will be based on
        """
        location = self.dataset.iloc[0][interlevel["dataset_field_name"]]

        choices = {}
        for index, row in reference_subset.reset_index().iterrows():
            if row["location"] not in choices:
                choices[row["location"]] = {}
            choices[row["location"]][row["index"]] = row.to_dict()

        matched_tuples = process.extractBests(location, choices.keys(),
                                              score_cutoff=SCORE_CUTOFF, limit=MAX_MATCHES)

        matches = pd.DataFrame()
        for matched_loc, score in matched_tuples:
            temp = {}
            temp[matched_loc] = choices[matched_loc]
            df = pd.DataFrame.from_dict(temp[matched_loc], orient="index")
            df["score"] = score
            matches = matches.append(df)

        if len(matches) and len(matches[matches["score"] == 100]):
            return matches[matches["score"] == 100].copy()

        return matches
