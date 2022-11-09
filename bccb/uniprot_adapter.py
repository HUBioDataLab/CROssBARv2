from time import time
import collections
from typing import Dict, List

from tqdm import tqdm  # progress bar
from pypath.share import curl, settings
from pypath.utils import mapping
from pypath.inputs import uniprot
from biocypher._logger import logger
import biocypher
from contextlib import ExitStack

import numpy as np
import pandas as pd

logger.debug(f"Loading module {__name__}.")


class Uniprot:
    def __init__(self, organism="*", rev=True):
        self.organism = organism
        self.rev = rev
        self.uniprot_df = None

    def download_uniprot_data(self, cache=False, debug=False, retries=3):
        """
        Wrapper function to download uniprot data using pypath; used to access
        settings.

        Args:
            cache: if True, it uses the cached version of the data, otherwise
            forces download.

            debug: if True, turns on debug mode in pypath.

            retries: number of retries in case of download error.
        """

        # add context managers to stack
        with ExitStack() as stack:

            stack.enter_context(settings.context(retries=retries))
            
            if debug:
                stack.enter_context(curl.debug_on)
            
            if not cache:
                stack.enter_context(curl.cache_off)

            self.uniprot_data_downloader()

    def uniprot_data_downloader(self):
        """
        Download uniprot data from uniprot.org through pypath.
        """

        t0 = time()

        self.attributes = [  # with query field keys in uniprot api
            # primary attributes
            "length",
            "mass",
            "organism",
            "organism-id",
            "protein names",
            "proteome",
            "genes",
            "ec",
            "database(Ensembl)",
            # xref attributes
            "database(GeneID)",
            "virus hosts",
            "database(KEGG)",
        ]

        # download all swissprot ids
        self.uniprot_ids = list(uniprot._all_uniprots(self.organism, self.rev))

        # download attribute dicts
        self.data = {}
        for query_key in tqdm(self.attributes):
            self.data[query_key] = uniprot.uniprot_data(
                query_key, self.organism, self.rev
            )

            logger.debug(f"{query_key} field is downloaded")

        secondary_ids = uniprot.get_uniprot_sec(None)
        self.data["secondary_ids"] = collections.defaultdict(list)
        for sec_id in secondary_ids:
            self.data["secondary_ids"][sec_id[1]].append(sec_id[0])
        for k, v in self.data["secondary_ids"].items():
            self.data["secondary_ids"][k] = ";".join(v)

        t1 = time()
        msg = (
            f"Acquired UniProt data in {round((t1-t0) / 60, 2)} mins."
        )
        logger.info(msg)

    def fields_splitter(self, field_key, field_value):
        """
        Split fields with multiple entries in uniprot
        Args:
            field_key: field name
            field_value: entry of the field
        """
        if field_value:
            # replace sensitive elements for admin-import
            field_value = (
                field_value.replace("|", ",").replace("'", "^").strip()
            )

            # define fields that will not be splitted by semicolon
            split_dict = {"proteome": ",", "genes": " "}

            # if field in split_dict split accordingly
            if field_key in split_dict.keys():
                field_value = field_value.split(split_dict[field_key])
                # if field has just one element in the list make it string
                if len(field_value) == 1:
                    field_value = field_value[0]

            # split semicolons (;)
            else:
                field_value = field_value.strip().strip(";").split(";")

                # split colons (":") in kegg field
                if field_key == "database(KEGG)":
                    _list = []
                    for e in field_value:
                        _list.append(e.split(":")[1].strip())
                    field_value = _list

                # take first element in database(GeneID) field
                if field_key == "database(GeneID)":
                    field_value = field_value[0]

                # if field has just one element in the list make it string
                if isinstance(field_value, list) and len(field_value) == 1:
                    field_value = field_value[0]

            return field_value

        else:
            return None

    def split_protein_names_field(self, field_value):
        """
        Split protein names field in uniprot
        Args:
            field_value: entry of the protein names field
        Example:
            "Acetate kinase (EC 2.7.2.1) (Acetokinase)" -> ["Acetate kinase", "Acetokinase"]
        """
        field_value = field_value.replace("|", ",").replace(
            "'", "^"
        )  # replace sensitive elements

        if "[Cleaved" in field_value:
            # discarding part after the "[Cleaved"
            clip_index = field_value.index("[Cleaved")
            protein_names = (
                field_value[:clip_index].replace("(Fragment)", "").strip()
            )

            # handling multiple protein names
            if "(EC" in protein_names[0]:
                splitted = protein_names[0].split(" (")
                protein_names = []

                for name in splitted:
                    if not name.strip().startswith("EC"):
                        if not name.strip().startswith("Fragm"):
                            protein_names.append(name.rstrip(")").strip())

            elif " (" in protein_names[0]:
                splitted = protein_names[0].split(" (")
                protein_names = []
                for name in splitted:
                    if not name.strip().startswith("Fragm"):
                        protein_names.append(name.rstrip(")").strip())

        elif "[Includes" in field_value:
            # discarding part after the "[Includes"
            clip_index = field_value.index("[Includes")
            protein_names = (
                field_value[:clip_index].replace("(Fragment)", "").strip()
            )
            # handling multiple protein names
            if "(EC" in protein_names[0]:

                splitted = protein_names[0].split(" (")
                protein_names = []

                for name in splitted:
                    if not name.strip().startswith("EC"):
                        if not name.strip().startswith("Fragm"):
                            protein_names.append(name.rstrip(")").strip())

            elif " (" in protein_names[0]:
                splitted = protein_names[0].split(" (")
                protein_names = []
                for name in splitted:
                    if not name.strip().startswith("Fragm"):
                        protein_names.append(name.rstrip(")").strip())

        # handling multiple protein names
        elif "(EC" in field_value.replace("(Fragment)", ""):
            splitted = field_value.split(" (")
            protein_names = []

            for name in splitted:
                if not name.strip().startswith("EC"):
                    if not name.strip().startswith("Fragm"):
                        protein_names.append(name.rstrip(")").strip())

        elif " (" in field_value.replace("(Fragment)", ""):
            splitted = field_value.split(" (")
            protein_names = []
            for name in splitted:
                if not name.strip().startswith("Fragm"):
                    protein_names.append(name.rstrip(")").strip())

        else:
            protein_names = field_value.replace("(Fragment)", "").strip()

        return protein_names

    def split_virus_hosts_field(self, field_value):
        """
        Split virus hosts fields in uniprot

        Args:
            field_value: entry of the virus hosts field

        Example:
            "Pyrobaculum arsenaticum [TaxID: 121277]; Pyrobaculum oguniense [TaxID: 99007]" -> ['121277', '99007']
        """
        if field_value:
            if ";" in field_value:
                splitted = field_value.split(";")
                virus_hosts_tax_ids = []
                for v in splitted:
                    virus_hosts_tax_ids.append(
                        v[v.index("[") + 1 : v.index("]")].split(":")[1].strip()
                    )
            else:
                virus_hosts_tax_ids = (
                    field_value[
                        field_value.index("[") + 1 : field_value.index("]")
                    ]
                    .split(":")[1]
                    .strip()
                )

            return virus_hosts_tax_ids
        else:
            return None

    def ensembl_process(self, ens_list):
        """
        take ensembl transcript ids, return ensembl gene ids by using pypath mapping tool

        Args:
            field_value: ensembl transcript list

        """

        listed_enst = []
        if isinstance(ens_list, str):
            listed_enst.append(ens_list)
        else:
            listed_enst = ens_list

        listed_enst = [enst.split(" [")[0] for enst in listed_enst]

        ensg_ids = set()
        for enst_id in listed_enst:
            ensg_id = list(
                mapping.map_name(
                    enst_id.split(".")[0], "enst_biomart", "ensg_biomart"
                )
            )
            ensg_id = ensg_id[0] if ensg_id else None
            if ensg_id:
                ensg_ids.add(ensg_id)

        ensg_ids = list(ensg_ids)

        if len(ensg_ids) == 1:
            ensg_ids = ensg_ids[0]

        if len(listed_enst) == 1:
            listed_enst = listed_enst[0]

        return listed_enst, ensg_ids

    def get_uniprot_nodes(self) -> List[Dict]:
        """
        Get nodes from UniProt data.
        """

        logger.info("Preparing nodes.")

        # define fields that need splitting
        split_fields = [
            "secondary_ids",
            "proteome",
            "genes",
            "ec",
            "database(GeneID)",
            "database(Ensembl)",
            "database(KEGG)",
        ]

        # define properties of nodes
        protein_properties = [
            "secondary_ids",
            "length",
            "mass",
            "protein names",
            "proteome",
            "ec",
            "virus hosts",
            "organism-id",
        ]
        gene_properties = [
            "genes",
            "database(GeneID)",
            "database(KEGG)",
            "database(Ensembl)",
            "ensembl_gene_ids",
        ]
        organism_properties = ["organism"]

        # add secondary_ids to self.attributes
        attributes = self.attributes + ["secondary_ids"]

        gene_id = str()

        # create list of nodes
        node_list = []

        for protein in tqdm(self.uniprot_ids):
            protein_id = "uniprot:" + protein
            _props = {}

            for arg in attributes:

                # split fields
                if arg in split_fields:
                    attribute_value = self.data.get(arg).get(protein)
                    if attribute_value:
                        _props[arg] = self.fields_splitter(arg, attribute_value)

                else:
                    attribute_value = self.data.get(arg).get(protein)
                    if attribute_value:
                        _props[arg] = (
                            attribute_value.replace("|", ",")
                            .replace("'", "^")
                            .strip()
                        )

                if arg == "database(Ensembl)" and arg in _props:
                    _props[arg], ensg_ids = self.ensembl_process(_props[arg])
                    if ensg_ids:
                        _props["ensembl_gene_ids"] = ensg_ids

                elif arg == "protein names":
                    _props[arg] = self.split_protein_names_field(
                        self.data.get(arg).get(protein)
                    )

                elif arg == "virus hosts":
                    attribute_value = self.split_virus_hosts_field(
                        self.data.get(arg).get(protein)
                    )
                    if attribute_value:
                        _props[arg] = attribute_value

            protein_props = dict()
            gene_props = dict()
            organism_props = dict()

            for k, v in _props.items():
                # define protein_properties
                if k in protein_properties:
                    # make length, mass and organism-id fields integer and replace hyphen in keys
                    if k in ["length", "mass", "organism-id"]:
                        protein_props[k.replace("-", "_")] = int(
                            _props[k].replace(",", "")
                        )
                        if k == "organism-id":
                            organism_id = "ncbitaxon:" + _props[k]

                    # replace hyphens and spaces with underscore
                    else:
                        protein_props[
                            k.replace(" ", "_").replace("-", "_")
                        ] = _props[k]

                # if genes and database(GeneID) fields exist, define gene_properties
                elif (
                    k in gene_properties
                    and "genes" in _props.keys()
                    and "database(GeneID)" in _props.keys()
                ):
                    if "database" in k:
                        # make ncbi gene id as gene_id
                        if "GeneID" in k:
                            gene_id = "ncbigene:" + _props[k]
                        # replace parantheses in field names and make their name lowercase
                        else:
                            gene_props[
                                k.split("(")[1].split(")")[0].lower()
                            ] = _props[k]

                    else:
                        gene_props[k] = _props[k]

                # define organism_properties
                elif k in organism_properties:
                    organism_props[k] = _props[k]

            # append related fields to protein_nodes
            node_list.append((protein_id, "protein", protein_props))

            # append related fields to gene_nodes and gene_to_protein_edges
            if gene_props:
                node_list.append((gene_id, "gene", gene_props))

            # append related fields to organism_nodes
            node_list.append((organism_id, "organism", organism_props))

        return node_list

    def get_uniprot_edges(self):
        """
        Get nodes and edges from UniProt data.
        """

        logger.info("Preparing edges.")

        # define fields that need splitting
        split_fields = [
            "secondary_ids",
            "proteome",
            "genes",
            "ec",
            "database(GeneID)",
            "database(Ensembl)",
            "database(KEGG)",
        ]

        # define properties of nodes
        protein_properties = [
            "secondary_ids",
            "length",
            "mass",
            "protein names",
            "proteome",
            "ec",
            "virus hosts",
            "organism-id",
        ]
        gene_properties = [
            "genes",
            "database(GeneID)",
            "database(KEGG)",
            "database(Ensembl)",
            "ensembl_gene_ids",
        ]

        # add secondary_ids to self.attributes
        attributes = self.attributes + ["secondary_ids"]

        gene_id = str()

        # create lists of edges
        edge_list = []

        for protein in tqdm(self.uniprot_ids):
            protein_id = "uniprot:" + protein
            _props = {}

            for arg in attributes:

                # split fields
                if arg in split_fields:
                    attribute_value = self.data.get(arg).get(protein)
                    if attribute_value:
                        _props[arg] = self.fields_splitter(arg, attribute_value)

                else:
                    attribute_value = self.data.get(arg).get(protein)
                    if attribute_value:
                        _props[arg] = (
                            attribute_value.replace("|", ",")
                            .replace("'", "^")
                            .strip()
                        )

                if arg == "database(Ensembl)" and arg in _props:
                    _props[arg], ensg_ids = self.ensembl_process(_props[arg])
                    if ensg_ids:
                        _props["ensembl_gene_ids"] = ensg_ids

                elif arg == "protein names":
                    _props[arg] = self.split_protein_names_field(
                        self.data.get(arg).get(protein)
                    )

                elif arg == "virus hosts":
                    attribute_value = self.split_virus_hosts_field(
                        self.data.get(arg).get(protein)
                    )
                    if attribute_value:
                        _props[arg] = attribute_value

            for k in _props.keys():
                # define protein_properties
                if k in protein_properties:
                    # make organism-id field integer and replace hyphen in keys
                    if k == "organism-id":
                        organism_id = "ncbitaxon:" + _props[k]

                # if genes and database(GeneID) fields exist, define gene_properties
                elif (
                    k in gene_properties
                    and "genes" in _props.keys()
                    and "database(GeneID)" in _props.keys()
                ):
                    if "database" in k:
                        # make ncbi gene id as gene_id
                        if "GeneID" in k:
                            gene_id = "ncbigene:" + _props[k]

            # append related fields to gene_nodes and gene_to_protein_edges
            if gene_id:
                edge_list.append((gene_id, protein_id, "Encodes", dict()))

            # append related fields to protein_to_organism_edges
            if organism_id:
                edge_list.append(
                    (protein_id, organism_id, "Belongs_To", dict())
                )

        return edge_list
