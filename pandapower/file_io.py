# -*- coding: utf-8 -*-

# Copyright (c) 2016-2017 by University of Kassel and Fraunhofer Institute for Wind Energy and
# Energy System Technology (IWES), Kassel. All rights reserved. Use of this source code is governed
# by a BSD-style license that can be found in the LICENSE file.

import json
import numbers
import os
import sys
import pickle

import copy

try:
    from fiona.crs import from_epsg
    from geopandas import GeoDataFrame, GeoSeries
    from shapely.geometry import Point, LineString
    GEOPANDAS_INSTALLED = True
except:
    GEOPANDAS_INSTALLED = False

from pandas import lib

import pandas as pd

import numpy

from pandapower.auxiliary import pandapowerNet
from pandapower.toolbox import convert_format
from pandapower.html_net import _net_to_html
from pandapower.io_utils import *
from pandas.core.common import _maybe_box_datetimelike


def to_pickle(net, filename):
    """
    Saves a pandapower Network with the pickle library.

    INPUT:
        **net** (dict) - The pandapower format network

        **filename** (string) - The absolute or relative path to the output file or an writable file-like objectxs

    EXAMPLE:

        >>> pp.to_pickle(net, os.path.join("C:", "example_folder", "example1.p"))  # absolute path
        >>> pp.to_pickle(net, "example2.p")  # relative path

    """
    if hasattr(filename, 'write'):
        pickle.dump(dict(net), filename, protocol=2)
        return
    if not filename.endswith(".p"):
        raise Exception("Please use .p to save pandapower networks!")
    save_net = dict()
    for key, item in net.items():
        if key != "_is_elements":
            if hasattr(item, "columns") and "geometry" in item.columns:
                # we convert shapely-objects to primitive data-types on a deepcopy
                item = copy.deepcopy(item)
                if key == "bus_geodata" and not isinstance(item.geometry.values[0], tuple):
                    item["geometry"] = item.geometry.apply(lambda x: (x.x, x.y))
                elif key == "line_geodata" and not isinstance(item.geometry.values[0], list):
                    item["geometry"] = item.geometry.apply(lambda x: list(x.coords))

            save_net[key] = {"DF": item.to_dict("split"), "dtypes": {col: dt
                            for col, dt in zip(item.columns, item.dtypes)}}  \
                            if isinstance(item, pd.DataFrame) else item

    with open(filename, "wb") as f:
        pickle.dump(save_net, f, protocol=2) #use protocol 2 for py2 / py3 compatibility


def to_excel(net, filename, include_empty_tables=False, include_results=True):
    """
    Saves a pandapower Network to an excel file.

    INPUT:
        **net** (dict) - The pandapower format network

        **filename** (string) - The absolute or relative path to the output file

    OPTIONAL:
        **include_empty_tables** (bool, False) - empty element tables are saved as excel sheet

        **include_results** (bool, True) - results are included in the excel sheet

    EXAMPLE:

        >>> pp.to_excel(net, os.path.join("C:", "example_folder", "example1.xlsx"))  # absolute path
        >>> pp.to_excel(net, "example2.xlsx")  # relative path

    """
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    for item, table in net.items():
        if item == "bus_geodata":
            if "geometry" in table.columns:
                df_dict = {"x": table.x, "y": table.y,
                           "geometry_x": [x.x for x in net.bus_geodata.geometry],
                           "geometry_y": [x.y for x in net.bus_geodata.geometry]}
                table = pd.DataFrame.from_dict(df_dict)
            else:
                table = pd.DataFrame(table[["x", "y"]])
        if type(table) != pd.DataFrame or item.startswith("_"):
            continue
        elif item.startswith("res"):
            if include_results and len(table) > 0:
                table.to_excel(writer, sheet_name=item)
        elif item == "line_geodata":
            geo = pd.DataFrame(index=table.index)
            for i, coord in table.iterrows():
                for nr, (x, y) in enumerate(coord.coords):
                    geo.loc[i, "x%u" % nr] = x
                    geo.loc[i, "y%u" % nr] = y
            geo.to_excel(writer, sheet_name=item)
        elif len(table) > 0 or include_empty_tables:
            table.to_excel(writer, sheet_name=item)
    parameters = pd.DataFrame(index=["name", "f_hz", "version"], columns=["parameters"],
                              data=[net.name, net.f_hz, net.version])
    pd.DataFrame(net.std_types["line"]).T.to_excel(writer, sheet_name="line_std_types")
    pd.DataFrame(net.std_types["trafo"]).T.to_excel(writer, sheet_name="trafo_std_types")
    pd.DataFrame(net.std_types["trafo3w"]).T.to_excel(writer, sheet_name="trafo3w_std_types")
    parameters.to_excel(writer, sheet_name="parameters")
    writer.save()


def to_json_string(net):
    """
        Returns a pandapower Network in JSON format. The index columns of all pandas DataFrames will
        be saved in ascending order. net elements which name begins with "_" (internal elements)
        will not be saved. Std types will also not be saved.

        INPUT:
            **net** (dict) - The pandapower format network

            **filename** (string) - The absolute or relative path to the input file.

        EXAMPLE:

             >>> json = pp.to_json_string(net)

    """
    json_string = "{"
    for k in sorted(net.keys()):
        if k[0] == "_":
            continue
        if isinstance(net[k], pd.DataFrame):
            json_string += '"%s":%s,' % (k, net[k].to_json(orient="columns"))
        elif isinstance(net[k], numpy.ndarray):
            json_string += k + ":" + json.dumps(net[k].tolist()) + ","
        elif isinstance(net[k], dict):
            json_string += '"%s":%s,' % (k, json.dumps(net[k]))
        elif isinstance(net[k], bool):
            json_string += '"%s":%s,' % (k, "true" if net[k] else "false")
        elif isinstance(net[k], str):
            json_string += '"%s":"%s",' % (k, net[k])
        elif isinstance(net[k], numbers.Number):
            json_string += '"%s":%s,' % (k, net[k])
        elif net[k] is None:
            json_string += '"%s":null,' % k
        else:
            raise UserWarning("could not detect type of %s" % k)
    json_string = json_string[:-1] + "}\n"
    return json_string


def to_json(net, filename=None):
    """
        Saves a pandapower Network in JSON format. The index columns of all pandas DataFrames will
        be saved in ascending order. net elements which name begins with "_" (internal elements)
        will not be saved. Std types will also not be saved.

        INPUT:
            **net** (dict) - The pandapower format network

            **filename** (string or file) - The absolute or relative path to the output file or file-like object

        EXAMPLE:

             >>> pp.to_json(net, "example.json")

    """
    dict_net = to_dict_of_dfs(net, include_results=False, create_dtype_df=True)
    dict_net["dtypes"] = collect_all_dtypes_df(net)
    json_string = to_json_string(dict_net)
    if hasattr(filename, 'write'):
        filename.write(json_string)
        return
    with open(filename, "w") as text_file:
        text_file.write(json_string)


def to_sql(net, con, include_empty_tables=False, include_results=True):
    dodfs = to_dict_of_dfs(net, include_results=include_results)
    dodfs["dtypes"] = collect_all_dtypes_df(net)
    for name, data in dodfs.items():
        data.to_sql(name, con, if_exists="replace")


def to_sqlite(net, filename):
    import sqlite3
    conn = sqlite3.connect(filename)
    to_sql(net, conn)
    conn.close()


def from_pickle(filename, convert=True):
    """
    Load a pandapower format Network from pickle file

    INPUT:
        **filename** (string or file) - The absolute or relative path to the input file or file-like object

    OUTPUT:
        **net** (dict) - The pandapower format network

    EXAMPLE:

        >>> net1 = pp.from_pickle(os.path.join("C:", "example_folder", "example1.p")) #absolute path
        >>> net2 = pp.from_pickle("example2.p") #relative path

    """
    def read(f):
        if sys.version_info >= (3,0):
            return pickle.load(f, encoding='latin1')
        else:
            return pickle.load(f)
    if hasattr(filename, 'read'):
        net = read(filename)
    elif not os.path.isfile(filename):
        raise UserWarning("File %s does not exist!!" % filename)
    else:
        with open(filename, "rb") as f:
            net = read(f)
    net = pandapowerNet(net)

    try:
        epsg = net.gis_epsg_code
    except AttributeError:
        epsg = None

    for key, item in net.items():
        if isinstance(item, dict) and "DF" in item:
            df_dict = item["DF"]
            if "columns" in df_dict:
                if GEOPANDAS_INSTALLED and "geometry" in df_dict["columns"] \
                        and epsg is not None:
                    # convert primitive data-types to shapely-objects
                    if key == "bus_geodata":
                        data = {"x": [row[0] for row in df_dict["data"]],
                                "y": [row[1] for row in df_dict["data"]]}
                        geo = [Point(row[2][0], row[2][1]) for row in df_dict["data"]]
                    elif key == "line_geodata":
                        data = {"coords": [row[0] for row in df_dict["data"]]}
                        geo = [LineString(row[1]) for row in df_dict["data"]]

                    net[key] = GeoDataFrame(data, crs=from_epsg(epsg), geometry=geo,
                                            index=df_dict["index"])
                else:
                    net[key] = pd.DataFrame(columns=df_dict["columns"], index=df_dict["index"],
                                            data=df_dict["data"])
            else:
                # TODO: is this legacy code?
                net[key] = pd.DataFrame.from_dict(df_dict)
                if "columns" in item:
                    net[key] = net[key].reindex_axis(item["columns"], axis=1)

            if "dtypes" in item:
                if "geometry" in df_dict["columns"]:
                    pass
                else:
                    try:
                        #only works with pandas 0.19 or newer
                        net[key] = net[key].astype(item["dtypes"])
                    except:
                        #works with pandas <0.19
                        for column in net[key].columns:
                            net[key][column] = net[key][column].astype(item["dtypes"][column])
    if convert:
        convert_format(net)
    return net


def from_excel(filename, convert=True):
    """
    Load a pandapower network from an excel file

    INPUT:
        **filename** (string) - The absolute or relative path to the input file.

    OUTPUT:
        **convert** (bool) - use the convert format function to

        **net** (dict) - The pandapower format network

    EXAMPLE:

        >>> net1 = pp.from_excel(os.path.join("C:", "example_folder", "example1.xlsx")) #absolute path
        >>> net2 = pp.from_excel("example2.xlsx") #relative path

    """

    if not os.path.isfile(filename):
        raise UserWarning("File %s does not exist!!" % filename)
    xls = pd.ExcelFile(filename).parse(sheetname=None)
    par = xls["parameters"]["parameters"]
    name = None if pd.isnull(par.at["name"]) else par.at["name"]
    net = create_empty_network(name=name, f_hz=par.at["f_hz"])

    for item, table in xls.items():
        if item == "parameters":
            continue
        elif item.endswith("std_types"):
            item = item.split("_")[0]
            for std_type, tab in table.iterrows():
                net.std_types[item][std_type] = dict(tab)
        elif item == "line_geodata":
            points = int(len(table.columns) / 2)
            for i, coords in table.iterrows():
                coord = [(coords["x%u" % nr], coords["y%u" % nr]) for nr in range(points)
                         if pd.notnull(coords["x%u" % nr])]
                net.line_geodata.loc[i, "coords"] = coord
        else:
            net[item] = table
#    net.line.geodata.coords.
    if convert:
        convert_format(net)
    return net


def from_json(filename, convert=True):
    """
    Load a pandapower network from a JSON file.
    The index of the returned network is not necessarily in the same order as the original network.
    Index columns of all pandas DataFrames are sorted in ascending order.

    INPUT:
        **filename** (string or file) - The absolute or relative path to the input file or file-like object

    OUTPUT:
        **convert** (bool) - use the convert format function to

        **net** (dict) - The pandapower format network

    EXAMPLE:

        >>> net = pp.from_json("example.json")

    """
    if hasattr(filename, 'read'):
        data = json.load(filename)
    elif not os.path.isfile(filename):
        raise UserWarning("File %s does not exist!!" % filename)
    else:
        with open(filename) as data_file:
            data = json.load(data_file)
    try:
        pd_dicts = dicts_to_pandas(data)
        net = from_dict_of_dfs(pd_dicts)
        restore_all_dtypes(net, pd_dicts["dtypes"])
        if convert:
            convert_format(net)
        return net
    except UserWarning:
        # Can be deleted in the future, maybe now
        return from_json_dict(data, convert=convert)


def from_json_string(json_string, convert=True):
    """
    Load a pandapower network from a JSON string.
    The index of the returned network is not necessarily in the same order as the original network.
    Index columns of all pandas DataFrames are sorted in ascending order.

    INPUT:
        **json_string** (string) - The json string representation of the network

    OUTPUT:
        **convert** (bool) - use the convert format function to

        **net** (dict) - The pandapower format network

    EXAMPLE:

        >>> net = pp.from_json_string(json_str)

    """
    data = json.loads(json_string)
    return from_json_dict(data, convert=convert)


def from_json_dict(json_dict, convert=True):
    """
    Load a pandapower network from a JSON string.
    The index of the returned network is not necessarily in the same order as the original network.
    Index columns of all pandas DataFrames are sorted in ascending order.

    INPUT:
        **json_dict** (json) - The json object representation of the network

    OUTPUT:
        **convert** (bool) - use the convert format function to

        **net** (dict) - The pandapower format network

    EXAMPLE:

        >>> net = pp.pp.from_json_dict(json.loads(json_str))

    """
    net = create_empty_network(name=json_dict["name"], f_hz=json_dict["f_hz"])

    # checks if field exists in empty network and if yes, matches data type
    def check_equal_type(name):
        if name in net:
            if isinstance(net[name], type(json_dict[name])):
                return True
            elif isinstance(net[name], pd.DataFrame) and isinstance(json_dict[name], dict):
                return True
            else:
                return False
        return True

    for k in sorted(json_dict.keys()):
        if not check_equal_type(k):
            raise UserWarning("Different data type for existing pandapower field")
        if isinstance(json_dict[k], dict):
            if isinstance(net[k], pd.DataFrame):
                columns = net[k].columns
                net[k] = pd.DataFrame.from_dict(json_dict[k], orient="columns")
                net[k].set_index(net[k].index.astype(numpy.int64), inplace=True)
                net[k] = net[k][columns]
            else:
                net[k] = json_dict[k]
        else:
            net[k] = json_dict[k]
    if convert:
        convert_format(net)
    return net


def to_html(net, filename, respect_switches=True, include_lines=True, include_trafos=True, show_tables=True):
    """
    Saves a pandapower Network to an html file.

    INPUT:
        **net** (dict) - The pandapower format network

        **filename** (string) - The absolute or relative path to the input file.

    OPTIONAL:
        **respect_switches** (boolean, True) - True: open line switches are being considered
                                                     (no edge between nodes)
                                               False: open line switches are being ignored

        **include_lines** (boolean, True) - determines, whether lines get converted to edges

        **include_trafos** (boolean, True) - determines, whether trafos get converted to edges

        **show_tables** (boolean, True) - shows pandapower element tables

    """
    if not filename.endswith(".html"):
        raise Exception("Please use .html to save pandapower networks!")
    with open(filename, "w") as f:
        html_str = _net_to_html(net, respect_switches, include_lines, include_trafos, show_tables)
        f.write(html_str)
        f.close()


def from_sql(con):
    cursor = con.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    dodfs = dict()
    for t, in cursor.fetchall():
        table = pd.read_sql_query("SELECT * FROM %s" % t, con, index_col="index")
        table.index.name = None
        dodfs[t] = table
    net = from_dict_of_dfs(dodfs)
    restore_all_dtypes(net, dodfs["dtypes"])
    return net


def from_sqlite(filename, netname=""):
    import sqlite3
    con = sqlite3.connect(filename)
    net = from_sql(con)
    con.close()
    return net
