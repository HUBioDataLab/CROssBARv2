from __future__ import annotations

import collections
import csv
import re
import asyncio
import warnings

from concurrent.futures.thread import ThreadPoolExecutor

from abc import ABC, abstractmethod
from collections.abc import Iterable

import pypath.resources.urls as urls
from pypath.share import curl

_url = urls.urls['kegg_api']['url']

def gene_to_pathway(org):

    return _kegg_from_source_to_target('gene', 'pathway', org)


def pathway_to_gene(org):

    return _kegg_from_source_to_target('pathway', 'gene', org)


def gene_to_drug(org):

    return _kegg_from_source_to_target('gene', 'drug', org)


def drug_to_gene(org):

    return _kegg_from_source_to_target('drug', 'gene', org)


def gene_to_disease(org):

    return _kegg_from_source_to_target('gene', 'disease', org)


def disease_to_gene(org):

    return _kegg_from_source_to_target('disease', 'gene', org)


def pathway_to_drug():

    return _kegg_from_source_to_target('pathway', 'drug')


def drug_to_pathway():

    return _kegg_from_source_to_target('drug', 'pathway')


def pathway_to_disease():
    
    return _kegg_from_source_to_target('pathway', 'disease')


def disease_to_pathway():

    return _kegg_from_source_to_target('disease', 'pathway')


def disease_to_drug():

    return _kegg_from_source_to_target('disease', 'drug')


def drug_to_disease():
    
    return _kegg_from_source_to_target('drug', 'disease')


def drug_to_drug(
    drugs: list | tuple =None,
    join: bool=True, 
    asynchronous: bool=False
) -> tuple:
    """
    Downloads drug-drug interaction data from KEGG database.

    Arguments:
    @drugs: Drug IDs as a list or a tuple.
    @join: if it's True, returns individual interactions of queried list.
            Else, joins them together and returns mutual interactions.
    @asynchronous: This function yet to be implemented.
    """

    DrugToDrugInteraction = collections.namedtuple(
        'DrugToDrugInteraction', 
        (
            'type',
            'name',
            'interactions',
        ),
    )

    drug = _Drug()
    compound = _Compound()

    if asynchronous:
        warnings.warn('Async is not implemented for now. Defaulting to False...')
        asynchronous = False
    
    if drugs != None:

        entries = _kegg_ddi(drugs, join=join, asynchronous=asynchronous)

    else:
        drugIds = drug.get_data().keys()
        # Async will be false until it gets implemented properly
        entries = _kegg_ddi(drugIds, join=False, asynchronous=False)

    interactions = dict()

    for entry in entries:

        for i in range(2):

            try:
                entry_type, entry_id = entry[i].split(':')
            except ValueError:
                entry_type = entry[i][0]
                entry_id = entry[i]

            if entry_type == 'dr' or entry_type == 'D':

                entry_type = 'drug'
                entry_db = drug

            elif entry_type == 'cpd' or entry_type == 'C':

                entry_type = 'compound'
                entry_db = compound
            
            else:

                print(f'Unknown type \'{entry_type}\', exiting...')
                exit()

            try:

                entry_name = entry_db.get(entry_id)

            except:

                entry_name = None

            tmp_dict = {
                'type': entry_type,
                'id': entry_id,
                'name': entry_name
            }
            
            if i == 0:

                source = tmp_dict
            else:
                
                target = tmp_dict
        
        labels = entry[2].split(',')
        contraindication = True if 'CI' in labels else False
        precaution = True if 'P' in labels else False

        Interaction = collections.namedtuple(
                f'{target["type"].capitalize()}Interaction',
                (
                    'type',
                    'id',
                    'name',
                    'contraindication',
                    'precaution',
                )
        )

        interaction = Interaction(
                    target['type'],
                    target['id'],
                    target['name'],
                    contraindication,
                    precaution,
        )

        diseaseId = source['id']

        try:
            interactions[diseaseId]['interactions'].append(interaction)

        except KeyError:
            interactions[diseaseId] = dict()
            interactions[diseaseId]['type'] = source['type']
            interactions[diseaseId]['name'] = source['name']
            interactions[diseaseId]['interactions'] = [interaction]

    for key, value in interactions.items():

        interactions[key] = DrugToDrugInteraction(
            value['type'],
            value['name'],
            tuple(value['interactions']),
        )
    
    return interactions

def get_diseases(diseases):

    result = _kegg_get(diseases)

    DiseaseEntry = collections.namedtuple(
        'DiseaseEntry',
        (
            'db_links',
            'references',
        )
    )

    entries = list()

    db_links = dict()
    references = list()

    db_links_regex = r'(?:DBLINKS)?\s*([^:\s]+)\s*:\s*(.+)'
    db_links_matcher = re.compile(db_links_regex)

    references_regex = r'REFERENCE\s*([^\s]+)'
    references_matcher = re.compile(references_regex)

    state = None

    for line in result:

        line = line.strip(' ')

        if line.startswith('///'):
            entries.append(
                DiseaseEntry(
                    db_links,
                    references
                )
            )

            db_links = dict()
            references = list()
            state = None
        
        elif line.startswith('DBLINKS'):
            state = 'DBLINKS'
            key, value = db_links_matcher.findall(line)[0]
            if ' ' in value:
                value = value.split(' ')
            db_links[key] = value
        
        elif line.startswith('REFERENCE'):
            state = None
            if references_matcher.findall(line):
                reference = references_matcher.findall(line)[0]
                references.append(reference)
        
        else:
            if state == 'DBLINKS':
                key, value = db_links_matcher.findall(line)[0]
                if ' ' in value:
                    value = value.split(' ')
                db_links[key] = value
            else:
                continue
    
    return entries


def kegg_gene_id_to_ncbi_gene_id(org):

    return _kegg_conv(org, 'ncbi-geneid', target_split=True)


def ncbi_gene_id_to_kegg_gene_id(org):

    return _kegg_conv('ncbi-geneid', org, source_split=True)


def kegg_gene_id_to_uniprot_id(org):

    return _kegg_conv(org, 'uniprot', target_split=True)


def uniprot_id_to_kegg_gene_id(org):

    return _kegg_conv('uniprot', org, source_split=True)


def kegg_drug_id_to_chebi_id():

    return _kegg_conv('drug', 'chebi', source_split=True, target_split=True)


def chebi_id_to_kegg_drug_id():

    return _kegg_conv('chebi', 'drug', source_split=True, target_split=True)


def _kegg_general(operation, *arguments, split=True):

    url = _url % operation

    for argument in arguments:

        url += f'/{argument}'

    c = curl.Curl(url, silent = True, large = False)

    try:
        return [line.split('\t') if split else line for line in c.result.split('\n') if line]
    except AttributeError:
        return []


async def _kegg_general_async(operation, *arguments):

    #TODO Yet to be implemented
    # This function doesn't work but it better
    # stay so we can implement it without
    # changing the structure of the module

    return None

    url = _url % operation

    for argument in arguments:

        url += f'/{argument}'

    c = await curl.Curl(url, silent = True, large = False)

    try:
        return [line.split('\t') if split else line for line in c.result.split('\n') if line]
    except AttributeError:
        return []


def _kegg_list(database, option=None, org=None):

    if database == 'brite' and option != None:

        return _kegg_general('list', database, option)

    if database == 'pathway' and org != None:

        return _kegg_general('list', database, org)
    
    return _kegg_general('list', database)

def _kegg_get(db_entries: list | tuple | str):

    if isinstance(db_entries, list) or isinstance(db_entries, tuple):
        db_entries = '+'.join(db_entries)
    elif isinstance(db_entries, str):
        pass
    else:
        print(f'Unrecognized db_entries type: {type(db_entries)}')
        print('Exiting...')
        exit()
    
    return _kegg_general('get', db_entries, split=False)

def _kegg_conv(source_db, target_db, source_split=False, target_split=False):

    result = _kegg_general('conv', target_db, source_db)
    conversion_table = dict()
    keys = set()

    for index, entry in enumerate(result):

        source = entry[0]
        target = entry[1]

        if source_split:
            source = source.split(':')[1]

        if target_split:
            target = target.split(':')[1]

        if source in keys:
            try:
                conversion_table[source].append(target)
            except AttributeError:
                conversion_table[source] = [conversion_table[source]]
                conversion_table[source].append(target)
        else:
            conversion_table[source] = target

        keys.add(source)

    return conversion_table


def _kegg_link(source_db, target_db):

    return _kegg_general('link', target_db, source_db)


def _kegg_ddi(drugIds, join=True, asynchronous=False):

    if join and not isinstance(drugIds, str):

        drugIds = ['+'.join(drugIds)]

    if asynchronous:

        pool = ThreadPoolExecutor()

        return pool.submit(asyncio.run, _kegg_ddi_async(drugIds)).result()
        
    return _kegg_ddi_sync(drugIds)


def _kegg_ddi_sync(drugIds):

    result = list()

    if isinstance(drugIds, Iterable):

        for drugId in drugIds:

            result.extend(_kegg_general('ddi', drugId))

        return result


async def _kegg_ddi_async(drugIds):

    #TODO Yet to be implemented
    # This function doesn't work but it better
    # stay so we can implement it without
    # changing the structure of the module

    result = list()

    if isinstance(drugIds, Iterable):

        for response in asyncio.as_completed([_kegg_general_async('ddi', drugId) for drugId in drugIds]):
            response = await response
            result.extend(response)

        return result


def _kegg_from_source_to_target(source_db, target_db, org=None) -> tuple:

    db_name_list = [source_db, target_db]
    db_list = list()

    for db in db_name_list:

        if db == 'gene' and org != None:

            db_list.append(_Gene(org))

            kegg_to_ncbi = _KeggToNcbi(org)
            kegg_to_uniprot = _KeggToUniprot(org)

        elif db == 'pathway':

            db_list.append(_Pathway())

        elif db == 'disease':

            db_list.append(_Disease())

        elif db == 'drug':

            db_list.append(_Drug())

            kegg_to_chebi = _KeggToChebi()

        else:
            print('Problem in function call. Check arguments.')
            exit()
        
    if target_db == 'gene':
        TargetDbEntry = collections.namedtuple(
            f'{target_db.capitalize()}Entry',
            [
                f'{target_db}_id',
                f'{target_db}_name',
                'ncbi_gene_id',
                'uniprot_ids'
            ]
        )

    elif target_db == 'drug':
        TargetDbEntry = collections.namedtuple(
            f'{target_db.capitalize()}Entry',
            [
                f'{target_db}_id',
                f'{target_db}_name',
                'chebi_id',
            ]
        )

    else:
        TargetDbEntry = collections.namedtuple(
            f'{target_db.capitalize()}Entry',
            [
                f'{target_db}_id',
                f'{target_db}_name',
            ]
        )

    
    if source_db == 'gene':
        Interaction = collections.namedtuple(
            f'{source_db.capitalize()}To{target_db.capitalize()}Interaction',
            [
                f'{source_db}_name',
                f'{target_db.capitalize()}Entries',
                'ncbi_gene_id',
                'uniprot_ids'
            ]
        )

    elif source_db == 'drug':
        Interaction = collections.namedtuple(
            f'{source_db.capitalize()}To{target_db.capitalize()}Interaction',
            [
                f'{source_db}_name',
                f'{target_db.capitalize()}Entries',
                'chebi_id'
            ]
        )

    else:
        Interaction = collections.namedtuple(
            f'{source_db.capitalize()}To{target_db.capitalize()}Interaction',
            [
                f'{source_db}_name',
                f'{target_db.capitalize()}Entries',
            ]
        )

    source = db_list[0]
    target = db_list[1]

    source_url = source_db if source_db != 'gene' else org
    target_url = target_db if target_db != 'gene' else org

    entries = _kegg_link(source_url, target_url)
    interactions = dict()

    for entry in entries:

        source_id = source.handle(entry[0])

        try:
            source_name = source.get(source_id)
        except:
            source_name = None

        target_id = target.handle(entry[1])

        try:
            target_name = target.get(target_id)
        except:
            target_name = None

        if target_db == 'gene':

            ncbi_gene_id = kegg_to_ncbi.get(target_id)
            uniprot_ids = kegg_to_uniprot.get(target_id)

            if isinstance(ncbi_gene_id, list):
                ncbi_gene_id = tuple(ncbi_gene_id)

            if isinstance(uniprot_ids, list):
                uniprot_ids = tuple(uniprot_ids)

            target_db_entry = TargetDbEntry(
                target_id,
                target_name,
                ncbi_gene_id,
                uniprot_ids
            )
        
        elif target_db == 'drug':

            chebi_id = kegg_to_chebi.get(target_id)

            if isinstance(chebi_id, list):
                chebi_id = tuple(chebi_id)

            target_db_entry = TargetDbEntry(
                target_id,
                target_name,
                chebi_id
            )
        
        else:

            target_db_entry = TargetDbEntry(
                target_id,
                target_name,
            )

        try:
            interactions[source_id][f'{target_db}_entries'].append(target_db_entry)

        except KeyError:
            interactions[source_id] = dict()
            interactions[source_id][f'{source_db}_name'] = source_name
            interactions[source_id][f'{target_db}_entries'] = [target_db_entry]

            if source_db == 'gene':
                interactions[source_id]['ncbi_gene_id'] = kegg_to_ncbi.get(source_id)
                interactions[source_id]['uniprot_ids'] = kegg_to_uniprot.get(source_id)
            
            elif source_db == 'drug':
                interactions[source_id]['chebi_id'] = kegg_to_chebi.get(source_id)

    for key, value in interactions.items():

        if source_db == 'gene':
            interaction = Interaction (
                value[f'{source_db}_name'],
                tuple(value[f'{target_db}_entries']),
                value['ncbi_gene_id'],
                value['uniprot_ids']
            )
            
        elif source_db == 'drug':
            interaction = Interaction (
                value[f'{source_db}_name'],
                tuple(value[f'{target_db}_entries']),
                value['chebi_id'],
            )

        else:
            interaction = Interaction (
                value[f'{source_db}_name'],
                tuple(value[f'{target_db}_entries'])
            )

        interactions[key] = interaction

    if org != None:
        organism = _Organism()
        org_id, org_name = organism.get(org)
        interactions['org_id'] = org_id
        interactions['org_name'] = org_name

    return interactions


class _KeggDatabase(ABC):

    _data = None


    @abstractmethod
    def __init__(self):
        pass


    @abstractmethod
    def handle(self):
        pass


    @abstractmethod
    def download_data(self):
        pass


    def get(self, index):
        return self._data[index]


    def get_data(self):
        return self._data

    
class _Organism(_KeggDatabase):

    def __init__(self):
        self.download_data()


    def download_data(self):
        entries = _kegg_list('organism')
        self._data = {self.handle(org) : [org_id, org_name] for (org_id, org, org_name, _) in entries}


    def handle(self, org):
        return org


class _Gene(_KeggDatabase):

    def __init__(self, org):
        self.download_data(org)


    def download_data(self, org):

        entries = _kegg_list(org)
        
        gene_slice = [row[0] for row in entries]

        name_slice = [row[-1] for row in entries]
        name_slice = [name.split(';')[-1] for name in name_slice]
        name_slice = [name.strip(' ') for name in name_slice]

        entries = zip(gene_slice, name_slice)
        self._data = {self.handle(gene) : gene_name for (gene, gene_name) in entries}


    def handle(self, gene):

        return gene


class _Pathway(_KeggDatabase):

    def __init__(self, org=None):
        self.download_data()

    def download_data(self, org=None):

        if org != None:
        
            entries = _kegg_list('pathway', org)

        else:

            entries = _kegg_list('pathway')

        self._data = {self.handle(pathway) : pathway_name for (pathway, pathway_name) in entries}

    def handle(self, pathway):

        pathway_re = re.compile(r'\d+')
        pathway_id = pathway_re.search(pathway)

        return 'map' + pathway_id.group()


class _SplitDatabase(_KeggDatabase):
    def __init__(self, entry_url):
        self.download_data(entry_url)


    def download_data(self, entry_url):
        entries = _kegg_list(entry_url)
        self._data = {self.handle(entry) : entry_name for (entry, entry_name) in entries}


    def handle(self, entry):
        return entry.split(':')[1] if ":" in entry else entry


class _Disease(_SplitDatabase):

    def __init__(self):
        super().__init__('disease')


class _Drug(_SplitDatabase):

    def __init__(self):
        super().__init__('drug')

        
class _Compound(_SplitDatabase):

    def __init__(self):
        super().__init__('compound')


class _ConversionTable:

    _table = dict()

    def __init__(self):
        self.download_table()


    @abstractmethod
    def download_table(self):
        pass


    def get(self, index):
        try:
            return self._table[index]
        except KeyError:
            return None


    def get_table(self):
        return self._table


class _OrgTable(_ConversionTable):

    def __init__(self, org=None):
        if org != None:
            self.download_table(org)


class _KeggToNcbi(_OrgTable):
    
    def download_table(self, org):
        table = _kegg_conv(org, 'ncbi-geneid', target_split=True)
        self._table.update(table)


class _NcbiToKegg(_OrgTable):

    def download_table(self, org):
        table = _kegg_conv('ncbi-geneid', org, source_split=True)
        self._table.update(table)


class _KeggToUniprot(_OrgTable):

    def download_table(self, org):
        table = _kegg_conv(org, 'uniprot', target_split=True)
        self._table.update(table)


class _UniprotToKegg(_OrgTable):

    def download_table(self, org):
        table = _kegg_conv('uniprot', org, source_split=True)
        self._table.update(table)


class _KeggToChebi(_ConversionTable):

    def download_table(self):
        table = _kegg_conv('drug', 'chebi', source_split=True, target_split=True)
        self._table = table


class _ChebiToKegg(_ConversionTable):

    def download_table(self):
        table = _kegg_conv('chebi', 'drug', source_split=True, target_split=True)
        self._table = table
