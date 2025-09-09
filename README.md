
<div align="center">
  <picture>
    <!-- <source media="(prefers-color-scheme: light)" srcset="">
    <source media="(prefers-color-scheme: dark)" srcset=""> -->
    <source srcset="https://crossbarv2.hubiodatalab.com/static/images/crossbar-logo.svg">
    <img alt="CROssBARv2 logo" src="https://crossbarv2.hubiodatalab.com/static/images/crossbar-logo.svg">
  </picture>
</div>

<div align="center">
    <a href="https://crossbarv2.hubiodatalab.com"><img alt="website-badge" src="https://img.shields.io/website?url=https://crossbarv2.hubiodatalab.com/"></a>
    <a href="https://arxiv.org/abs/xxxx.xxxxx"><img alt="arxiv-badge" src="https://img.shields.io/badge/arXiv-xxxx.xxxxx-b31b1b.svg"></a>
    <img alt="github-star-badge" src="https://img.shields.io/github/stars/HUBioDataLab/CROssBARv2">
    <img alt="github-license-badge" src="https://img.shields.io/github/license/HUBioDataLab/CROssBARv2">
</div>
<br>

# CROssBARv2: A Unified Biomedical Knowledge Graph for Heterogeneous Data Representation and LLM-Driven Exploration

## Abstract

Biomedical discovery is hindered by fragmented, modality-specific repositories and uneven metadata, limiting integrative analysis, accessibility, and reproducibility. We present CROssBARv2, a provenance-rich biomedical data-and-knowledge integration platform that unifies heterogeneous sources into a maintainable, queryable system. By consolidating diverse data sources into an extensive knowledge graph enriched with ontologies, metadata, and deep learning-based vector embeddings, the system eliminates the need for researchers to navigate multiple, siloed databases and enables users to uncover novel insights. CROssBARv2 provides programmatic access, interactive exploration, embedding-based semantic search, and an intuitive natural language interface powered by large language models (LLMs). We assess CROssBARv2 through (i) multiple use-case analyses to test biological coherence; (ii) knowledge-augmented biomedical question-answering benchmarks comparing CROssBAR-LLM with up-to-date generalist LLMs; and (iii) a deep-learning–based predictive-modelling validation experiment for protein-function prediction using heterogeneous CROssBARv2 data. Collectively, CROssBARv2 offers a scalable and user-friendly foundation that facilitates hypothesis generation, knowledge discovery, and translational research.

## CROssBARv2 Workflow Overview

![Pipeline overview](images/workflow.png)

**Figure 1. Overview of the CROssBARv2 workflow.** (a) Integration of data from 34 well-established sources covering various biomedical domains. (b) Automatic retrieval, standardisation, and integration of source data using modular adapter scripts. (c) CROssBARv2 KG schema, comprising 14 node types and 51 edge types. (d) Storage of the KG in a Neo4j graph database, along with rich metadata and node embeddings computed using deep learning-based methods. (e) Execution of the CROssBAR-LLM workflow, which translates natural language queries into Cypher, executes the queries on KG, and synthesizes structured results into natural language responses; also supports vector-based similarity search. (f) Exploration of the KG through three interfaces: natural language querying via LLM interface, programmatic access via GraphQL API, and interactive visual exploration via the Neo4j browser.

# Download / Usage

To clone this repository:

```bash
git clone --recurse-submodules https://github.com/HUBioDataLab/CROssBARv2
```

## CROssBARv2 Knowledge Graph

Check the relevant [README](CROssBARv2-KG/README.md).

## CROssBARv2 Compose

This repository contains the unified docker compose file, of the services below.

Check the relevant [README](crossbar-compose/README.md).

## CROssBARv2 LLM

This repository contains the CROssBARv2 LLM.

Check the relevant [README](CROssBAR_LLM/README.md).

## CROssBARv2 GraphQL

This repository contains the GraphQL API interface of CROssBARv2 KG, which is useful for programmatic data retrieval.

Check the relevant [README](crossbar-graphql/README.md).

## CROssBARv2 Browser

You can browse our KG with Neo4j.

## CROssBARv2 TLS Dumper

This repository contains the necessary TLS utils, to host Neo4j with Traefik.

Check the relevant [README](crossbar-tls-dumper/README.md).
