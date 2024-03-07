from __future__ import annotations
from pypath.share import curl, settings

from pypath.inputs import sider, drugbank, offsides, adrecs

from contextlib import ExitStack

from bioregistry import normalize_curie
from tqdm import tqdm
from time import time
import os

from enum import Enum, EnumMeta, auto
from typing import Union

import pandas as pd
import numpy as np

from biocypher._logger import logger

from pydantic import BaseModel, DirectoryPath, EmailStr, validate_call

logger.debug(f"Loading module {__name__}.")


class SideEffectEnumMeta(EnumMeta):
    def __contains__(cls, item):
        return item in cls.__members__.keys()


class SideEffectNodeField(Enum, metaclass=SideEffectEnumMeta):
    NAME = "name"
    SYNONYMS = "synonyms"

    @classmethod
    def _missing_(cls, value: str):
        value = value.lower()
        for member in cls.__members__.values():
            if member.value.lower() == value:
                return member
        return None


class DrugSideEffectEdgeField(Enum, metaclass=SideEffectEnumMeta):
    SOURCE = "source"
    FREQUENCY = "frequency"
    PROPORTIONAL_REPORTING_RATIO = "proportional_reporting_ratio"

    @classmethod
    def _missing_(cls, value: str):
        value = value.lower()
        for member in cls.__members__.values():
            if member.value.lower() == value:
                return member
        return None


class SideEffectEdgeType(Enum, metaclass=SideEffectEnumMeta):
    DRUG_TO_SIDE_EFFECT = auto()
    SIDE_EFFECT_HIERARCHICAL_ASSOCIATION = auto()


class SideEffectModel(BaseModel):
    drugbank_user: EmailStr
    drugbank_passwd: str
    side_effect_node_fields: Union[list[SideEffectNodeField], None] = None
    drug_side_effect_edge_fields: Union[list[DrugSideEffectEdgeField], None] = None
    edge_types: Union[list[SideEffectEdgeType], None] = None
    test_mode: bool = False
    export_csv: bool = False
    output_dir: DirectoryPath | None = None
    add_prefix: bool = True


class SideEffect:
    def __init__(
        self,
        drugbank_user: EmailStr,
        drugbank_passwd: str,
        side_effect_node_fields: Union[list[SideEffectNodeField], None] = None,
        drug_side_effect_edge_fields: Union[list[DrugSideEffectEdgeField], None] = None,
        edge_types: Union[list[SideEffectEdgeType], None] = None,
        test_mode: bool = False,
        export_csv: bool = False,
        output_dir: DirectoryPath | None = None,
        add_prefix: bool = True,
    ):

        model = SideEffectModel(
            drugbank_user=drugbank_user,
            drugbank_passwd=drugbank_passwd,
            side_effect_node_fields=side_effect_node_fields,
            drug_side_effect_edge_fields=drug_side_effect_edge_fields,
            edge_types=edge_types,
            test_mode=test_mode,
            export_csv=export_csv,
            output_dir=output_dir,
            add_prefix=add_prefix,
        ).model_dump()

        self.drugbank_user = model["drugbank_user"]
        self.drugbank_passwd = model["drugbank_passwd"]
        self.add_prefix = model["add_prefix"]
        self.export_csv = model["export_csv"]
        self.output_dir = model["output_dir"]

        # set node fields
        self.set_node_fields(
            side_effect_node_fields=model["side_effect_node_fields"]
        )

        # set edge fields
        self.set_edge_fields(
            drug_side_effect_edge_fields=model["drug_side_effect_edge_fields"]
        )

        # set edge types
        self.set_edge_types(edge_types=model["edge_types"])

        # set early_stopping, if test_mode true
        self.early_stopping = None
        if model["test_mode"]:
            self.early_stopping = 100

    @validate_call
    def download_side_effect_data(
        self,
        cache: bool = False,
        debug: bool = False,
        retries: int = 3,
    ) -> None:
        """
        Wrapper function to download side effect data from various databases using pypath.
        Args
            cache: if True, it uses the cached version of the data, otherwise
            forces download.
            debug: if True, turns on debug mode in pypath.
            retries: number of retries in case of download error.
        """

        with ExitStack() as stack:
            stack.enter_context(settings.context(retries=retries))

            if debug:
                stack.enter_context(curl.debug_on())

            if not cache:
                stack.enter_context(curl.cache_off())

            self.dowload_sider_data()

            self.download_offsides_data()

            self.download_adrecs_data()

    def dowload_sider_data(self) -> None:

        logger.debug("Started downloading Sider data")
        t0 = time()

        sider_meddra_tsv = sider.sider_meddra_side_effects()
        self.meddra_id_to_side_effect_name = {
            i.meddra_id: i.side_effect_name for i in sider_meddra_tsv
        }

        if SideEffectEdgeType.DRUG_TO_SIDE_EFFECT in self.edge_types:
            self.umls_to_meddra_id = {
                i.cid: {"meddra_id": i.meddra_id, "name": i.side_effect_name}
                for i in sider_meddra_tsv
            }

            self.drugbank_data = drugbank.DrugbankFull(
                user=self.drugbank_user, passwd=self.drugbank_passwd
            )
            drugbank_drug_names = self.drugbank_data.drugbank_drugs_full(
                fields=["name"]
            )
            self.drugbank_name_to_drugbank_id_dict = {
                i.name.lower(): i.drugbank_id for i in drugbank_drug_names
            }

            sider_drug = sider.sider_drug_names()
            self.cid_to_sider_drug_name = {
                k: list(v)[0].name for k, v in sider_drug.items()
            }

            self.sider_meddra_with_freq = sider.sider_side_effect_frequencies()

        t1 = time()
        logger.info(
            f"Sider data is downloaded in {round((t1-t0) / 60, 2)} mins"
        )

    def download_offsides_data(self) -> None:
        logger.debug("Started downloading OffSides data")
        t0 = time()

        if SideEffectEdgeType.DRUG_TO_SIDE_EFFECT in self.edge_types:
            if not hasattr(self, "drugbank_data"):
                self.drugbank_data = drugbank.DrugbankFull(
                    user=self.drugbank_user, passwd=self.drugbank_passwd
                )

            drugbank_external_ids = (
                self.drugbank_data.drugbank_external_ids_full()
            )
            self.rxcui_to_drugbank = {
                v.get("RxCUI"): k
                for k, v in drugbank_external_ids.items()
                if v.get("RxCUI")
            }

        self.offsides_data = list(offsides.offsides_side_effects())

        t1 = time()
        logger.info(
            f"OffSides data is downloaded in {round((t1-t0) / 60, 2)} mins"
        )

    def download_adrecs_data(self) -> None:
        logger.debug("Started downloading ADReCS data")
        t0 = time()

        self.adrecs_terminology = adrecs.adrecs_adr_ontology()

        if SideEffectEdgeType.DRUG_TO_SIDE_EFFECT in self.edge_types:
            adrecs_drug_information = adrecs.adrecs_drug_identifiers()
            self.adrecs_drug_id_to_drugbank_id = {
                dr.badd: dr.drugbank
                for dr in adrecs_drug_information
                if dr.drugbank
            }

            self.adrecs_adr_id_to_adrecs_drug_id = {
                dr.adr_badd: dr.drug_badd for dr in adrecs.adrecs_drug_adr()
            }
            self.adrecs_adr_id_to_meddra_id = {
                entry.badd: str(entry.meddra)
                for entry in self.adrecs_terminology
            }

        if (
            SideEffectEdgeType.SIDE_EFFECT_HIERARCHICAL_ASSOCIATION
            in self.edge_types
        ):
            self.adrecs_ontology = adrecs.adrecs_hierarchy()

        t1 = time()
        logger.info(
            f"ADReCS data is downloaded in {round((t1-t0) / 60, 2)} mins"
        )

    def process_sider_drug_side_effect(self) -> pd.DataFrame:
        if not hasattr(self, "sider_meddra_with_freq"):
            self.dowload_sider_data()

        logger.debug("Started processing Sider drug-side effect data")
        t0 = time()

        df_list = []
        for cid, sider_with_freq in self.sider_meddra_with_freq.items():
            for interaction in sider_with_freq:
                if self.drugbank_name_to_drugbank_id_dict.get(
                    self.cid_to_sider_drug_name.get(cid)
                ) and self.umls_to_meddra_id.get(
                    interaction.umls_concept_in_meddra
                ):
                    drugbank_id = self.drugbank_name_to_drugbank_id_dict.get(
                        self.cid_to_sider_drug_name.get(cid)
                    )
                    meddra_id = self.umls_to_meddra_id[
                        interaction.umls_concept_in_meddra
                    ]["meddra_id"]

                    df_list.append(
                        (drugbank_id, meddra_id, interaction.frequency)
                    )

        df = pd.DataFrame(
            df_list, columns=["drugbank_id", "meddra_id", "frequency"]
        )

        df.drop_duplicates(
            subset=["drugbank_id", "meddra_id"], ignore_index=True, inplace=True
        )

        df["source"] = "Sider"

        t1 = time()
        logger.info(
            f"Sider drug-side effect data is processed in {round((t1-t0) / 60, 2)} mins"
        )

        return df

    def process_offsides_drug_side_effect(self) -> pd.DataFrame:
        if not hasattr(self, "offsides_data"):
            self.download_offsides_data()

        logger.debug("Started processing OffSides drug-side effect data")
        t0 = time()

        df_list = []
        for interaction in self.offsides_data:
            if (
                self.rxcui_to_drugbank.get(interaction.drug_rxnorn)
                and interaction.condition_meddra.isnumeric()
            ):
                df_list.append(
                    (
                        self.rxcui_to_drugbank[interaction.drug_rxnorn],
                        interaction.condition_meddra,
                        round(float(interaction.prr), 3),
                    )
                )

        df = pd.DataFrame(
            df_list,
            columns=[
                "drugbank_id",
                "meddra_id",
                "proportional_reporting_ratio",
            ],
        )

        df.drop_duplicates(
            subset=["drugbank_id", "meddra_id"], ignore_index=True, inplace=True
        )

        df["source"] = "OffSides"

        t1 = time()
        logger.info(
            f"OffSides drug-side effect data is processed in {round((t1-t0) / 60, 2)} mins"
        )

        return df

    def process_adrecs_drug_side_effect(self) -> pd.DataFrame:
        if not hasattr(self, "adrecs_terminology"):
            self.download_adrecs_data()

        logger.debug("Started processing ADReCS drug-side effect data")
        t0 = time()

        df_list = []
        for interaction in self.adrecs_terminology:
            if self.adrecs_drug_id_to_drugbank_id.get(
                self.adrecs_adr_id_to_adrecs_drug_id.get(interaction.badd)
            ):
                drugbank_id = self.adrecs_drug_id_to_drugbank_id[
                    self.adrecs_adr_id_to_adrecs_drug_id[interaction.badd]
                ]
                df_list.append(
                    (
                        drugbank_id,
                        str(interaction.meddra),
                    )
                )

        df = pd.DataFrame(df_list, columns=["drugbank_id", "meddra_id"])

        df.drop_duplicates(
            subset=["drugbank_id", "meddra_id"], ignore_index=True, inplace=True
        )

        df["source"] = "ADReCS"

        t1 = time()
        logger.info(
            f"ADReCS drug-side effect data is processed in {round((t1-t0) / 60, 2)} mins"
        )

        return df

    def merge_drug_side_effect_data(self) -> pd.DataFrame:
        adrecs_df = self.process_adrecs_drug_side_effect()

        sider_df = self.process_sider_drug_side_effect()

        offsides_df = self.process_offsides_drug_side_effect()

        logger.debug("Started merging drug-side effect edge data")
        t0 = time()

        merged_df = pd.merge(
            adrecs_df, sider_df, how="outer", on=["drugbank_id", "meddra_id"]
        )

        merged_df["source"] = merged_df[["source_x", "source_y"]].apply(
            self.merge_source_column, axis=1
        )

        merged_df.drop(columns=["source_x", "source_y"], inplace=True)

        merged_df = merged_df.merge(
            offsides_df, how="outer", on=["drugbank_id", "meddra_id"]
        )

        merged_df["source"] = merged_df[["source_x", "source_y"]].apply(
            self.merge_source_column, axis=1
        )

        merged_df.drop(columns=["source_x", "source_y"], inplace=True)

        t1 = time()
        logger.info(
            f"Drug-side effect edge data is merged in {round((t1-t0) / 60, 2)} mins"
        )

        # write drug-side effect edge data to csv
        if self.export_csv:
            if self.output_dir:
                full_path = os.path.join(
                    self.output_dir, "Drug_to_side_effect.csv"
                )
            else:
                full_path = os.path.join(os.getcwd(), "Drug_to_side_effect.csv")

            merged_df.to_csv(full_path, index=False)
            logger.info(
                f"Drug-side effect edge data data is written: {full_path}"
            )

        return merged_df

    @validate_call
    def get_nodes(self, label: str = "side_effect") -> list[tuple]:
        if not hasattr(self, "meddra_id_to_side_effect_name"):
            sider_meddra_tsv = sider.sider_meddra_side_effects()
            self.meddra_id_to_side_effect_name = {
                i.meddra_id: i.side_effect_name for i in sider_meddra_tsv
            }

        if not hasattr(self, "offsides_data"):
            self.offsides_data = offsides.offsides_side_effects()

        if not hasattr(self, "adrecs_terminology"):
            self.adrecs_terminology = adrecs.adrecs_adr_ontology()

        for entry in self.offsides_data:
            if (
                entry.condition_meddra
                not in self.meddra_id_to_side_effect_name.keys()
                and entry.condition_meddra.isnumeric()
            ):
                self.meddra_id_to_side_effect_name[entry.condition_meddra] = (
                    entry.condition
                )

        adr_synonyms_dict = {}
        for entry in self.adrecs_terminology:
            if (
                str(entry.meddra)
                not in self.meddra_id_to_side_effect_name.keys()
            ):
                self.meddra_id_to_side_effect_name[str(entry.meddra)] = (
                    entry.badd
                )

            if entry.synonyms:
                adr_synonyms_dict[str(entry.meddra)] = (
                    list(entry.synonyms)[0].replace("|", ",").replace("'", "^")
                    if len(entry.synonyms) == 1
                    else [
                        t.replace("|", ",").replace("'", "^")
                        for t in entry.synonyms
                    ]
                )

        logger.info("Started writing side effect nodes")

        node_list = []
        for index, (meddra_term, condition_name) in tqdm(
            enumerate(self.meddra_id_to_side_effect_name.items())
        ):
            props = {}

            if SideEffectNodeField.NAME.value in self.side_effect_node_fields:
                props[SideEffectNodeField.NAME.value] = (
                    condition_name.replace("|", ",")
                    .replace('"', "")
                    .replace("'", "^")
                )

            if (
                SideEffectNodeField.SYNONYMS.value
                in self.side_effect_node_fields
                and adr_synonyms_dict.get(meddra_term)
            ):
                props[SideEffectNodeField.SYNONYMS.value] = adr_synonyms_dict[
                    meddra_term
                ]

            meddra_id = self.add_prefix_to_id(
                prefix="meddra", identifier=meddra_term
            )
            node_list.append((meddra_id, label, props))

            if self.early_stopping and index + 1 == self.early_stopping:
                break

        # write pathway node data to csv
        if self.export_csv:
            if self.output_dir:
                full_path = os.path.join(self.output_dir, "Side_effect.csv")
            else:
                full_path = os.path.join(os.getcwd(), "Side_effect.csv")

            df_list = [
                {"meddra_id": meddra_id} | props
                for meddra_id, _, props in node_list
            ]
            df = pd.DataFrame.from_records(df_list)
            df.to_csv(full_path, index=False)
            logger.info(f"Side effect node data is written: {full_path}")

        return node_list

    def get_edges(self,
                drug_side_effect_label: str = "drug_has_side_effect",
                adrecs_side_effect_hierarchy_label: str = "side_effect_is_a_side_effect") -> list[tuple]:

        logger.info("Started writing ALL edge types")

        edge_list = []

        if (
            SideEffectEdgeType.SIDE_EFFECT_HIERARCHICAL_ASSOCIATION
            in self.edge_types
        ):
            edge_list.extend(self.get_drug_side_effect_edges(drug_side_effect_label))

        if SideEffectEdgeType.DRUG_TO_SIDE_EFFECT in self.edge_types:
            edge_list.extend(self.get_adrecs_side_effect_hierarchical_edges(adrecs_side_effect_hierarchy_label))

        return edge_list

    @validate_call
    def get_drug_side_effect_edges(
        self, label: str = "drug_has_side_effect"
    ) -> list[tuple]:
        drug_side_effect_edges_df = self.merge_drug_side_effect_data()

        logger.info("Started writing drug-side effect edges")

        edge_list = []
        for index, row in tqdm(
            drug_side_effect_edges_df.iterrows(),
            total=drug_side_effect_edges_df.shape[0],
        ):
            _dict = row.to_dict()

            meddra_id = self.add_prefix_to_id(
                prefix="meddra", identifier=_dict["meddra_id"]
            )
            drug_id = self.add_prefix_to_id(
                prefix="drugbank", identifier=_dict["drugbank_id"]
            )

            del _dict["meddra_id"], _dict["drugbank_id"]

            props = {}
            for k, v in _dict.items():
                if k in self.drug_side_effect_edge_fields and str(v) != "nan":
                    if isinstance(v, str) and "|" in v:
                        props[k] = v.split("|")
                    else:
                        props[k] = v

            edge_list.append((None, drug_id, meddra_id, label, props))

            if self.early_stopping and index + 1 == self.early_stopping:
                break

        return edge_list

    @validate_call
    def get_adrecs_side_effect_hierarchical_edges(
        self, label: str = "side_effect_is_a_side_effect"
    ) -> list[tuple]:
        if not hasattr(self, "adrecs_ontology"):
            self.download_adrecs_data()

        logger.info("Started writing side effect hierarchical edges")

        edge_list = []
        for index, relation in tqdm(enumerate(self.adrecs_ontology)):
            if self.adrecs_adr_id_to_meddra_id.get(
                relation.child.badd
            ) and self.adrecs_adr_id_to_meddra_id.get(relation.parent.badd):
                child_id = self.add_prefix_to_id(
                    prefix="meddra",
                    identifier=self.adrecs_adr_id_to_meddra_id[
                        relation.child.badd
                    ],
                )
                parent_id = self.add_prefix_to_id(
                    prefix="meddra",
                    identifier=self.adrecs_adr_id_to_meddra_id[
                        relation.parent.badd
                    ],
                )

                edge_list.append((None, child_id, parent_id, label, {}))

                if self.early_stopping and index + 1 == self.early_stopping:
                    break

        # write side effect hierarchical edge data to csv
        if self.export_csv:
            if self.output_dir:
                full_path = os.path.join(
                    self.output_dir, "Side_effect_hierarchy.csv"
                )
            else:
                full_path = os.path.join(
                    os.getcwd(), "Side_effect_hierarchy.csv"
                )

            df_list = [
                {"child_id": child_id, "parent_id": parent_id, "label": label}
                for _, child_id, parent_id, label, _ in edge_list
            ]
            df = pd.DataFrame.from_records(df_list)
            df.to_csv(full_path, index=False)
            logger.info(
                f"Side effect hierarchy edge data is written: {full_path}"
            )

        return edge_list

    @validate_call
    def add_prefix_to_id(
        self, prefix: str = None, identifier: str = None, sep: str = ":"
    ) -> str:
        """
        Adds prefix to database id
        """
        if self.add_prefix and identifier:
            return normalize_curie(prefix + sep + identifier)

        return identifier

    def merge_source_column(self, element, joiner="|"):

        _list = []
        for e in list(element.dropna().values):
            if joiner in e:
                _list.extend(iter(e.split(joiner)))
            else:
                _list.append(e)

        return joiner.join(list(dict.fromkeys(_list).keys()))

    def set_node_fields(self, side_effect_node_fields):
        if side_effect_node_fields:
            self.side_effect_node_fields = [
                field.value for field in side_effect_node_fields
            ]
        else:
            self.side_effect_node_fields = [
                field.value for field in SideEffectNodeField
            ]

    def set_edge_fields(self, drug_side_effect_edge_fields):
        if drug_side_effect_edge_fields:
            self.drug_side_effect_edge_fields = [
                field.value for field in drug_side_effect_edge_fields
            ]
        else:
            self.drug_side_effect_edge_fields = [
                field.value for field in DrugSideEffectEdgeField
            ]

    def set_edge_types(self, edge_types):
        self.edge_types = edge_types or list(SideEffectEdgeType)
