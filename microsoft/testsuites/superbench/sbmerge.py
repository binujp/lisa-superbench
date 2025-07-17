#!/usr/bin/python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Quick hack borrowing code from superbench.py to merge multiple runs on
the same setup. Code needs cleanup and a proper cli interface.

"skuinfo.json" has to be custom created for each run. Ideally this should
be extracted from logs or environment or command line, like we do when
superbench is run under lisa.
"""

import json
import os
import io
import csv
import re
import sys

from dataclasses import dataclass
from typing import Any
from datetime import datetime

class DashBoard:
    "BI Dashboard"
    __slots__ = ("Team",
                 "RunTimestamp",
                 "SessionType",
                 "HostMinroot",
                 "HostOSVersion",
                 "HostMemoryPartition",
                 "Hardware",
                 "VMType",
                 "VMOSVersion",
                 "L2Type",
                 "L2OS",
                 "VMSKU",
                 "ContainerCPU",
                 "ContainerMemory",
                 "ContainerConfiguration",
                 "ContainerImage",
                 "StorageConfiguration",
                 "NetworkConfiguration",
                 "GPUSKU",
                 "NumGPUsUsed",
                 "Category",
                 "Workload",
                 "WorkloadParameters",
                 "Benchmark",
                 "TraceDownloadLink",
                 "AdditionalInfo",
                 "cuda",
                 "GPUDriverVersion",
                 "TipSessionId",
                 "Metric",
                 "MetricValue",
                 "Scenario")

    def __init__(self, **kwargs):
        self.assign(**kwargs)

    def assign(self, **kwargs):
        for attr, value in kwargs.items():
            if attr in self.__slots__:
                setattr(self, attr, value)

    def header_csv(self):
        csv_line = io.StringIO()
        writer = csv.writer(csv_line, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(self.__slots__)
        return csv_line.getvalue().replace("AdditionalInfo", "Additional Info")

    def csv(self):
        csv_line = io.StringIO()
        writer = csv.writer(csv_line, quoting=csv.QUOTE_NONNUMERIC)
        values = [getattr(self, attr, "") for attr in self.__slots__]
        writer.writerow(values)
        return csv_line.getvalue()

class Superbench():
    # pylint: disable=C0301
    sku_file = "./skuinfo.json"

    def __init__(self, gpu, dist, log_path) -> None:
        print(f"Building dashboard csv for: {gpu} {dist} {log_path}")
        self.parse_results(gpu, dist, log_path)

    @staticmethod
    def dash_board_entry(sku_info):
        # pylint: disable=C0301
        additionalInfo = f"""{sku_info["tag"]}: {sku_info["os"]} {sku_info["driver version"]} {sku_info["gpu driver version"]} AL3/U22 sb comparison"""
        node_info_dict = { "Team" : "Azure Linux/Silicon",
                           "RunTimestamp" : datetime.now().strftime("%Y-%m-%d %H:%M"),
                           "VMType" : "L1VM",
                           "VMOSVersion" : sku_info["os"],
                           "VMSKU" : sku_info["sku"],
                           "GPUSKU" : sku_info["gpu"],
                           "NumGPUsUsed" : sku_info["count"],
                           "Category" : "GPU Runtime",
                           "Workload" : "Superbench",
                           "AdditionalInfo" : additionalInfo,
                           "cuda" : sku_info["driver version"],
                           "GPUDriverVersion" : sku_info["gpu driver version"],
                           "Scenario" : "Ubuntu vs AL3 HPC image performance comparison" }
        return DashBoard(**node_info_dict)

    @staticmethod
    def write_result(result_json, dashboard, db_csv_fd):
        result_json.pop("node")
        for key, value in result_json.items():
            if key.startswith("monitor/gpu"):
                continue

            # Strip gpu number
            test_name = re.sub(r":\d+", "", key)

            # Skip entries for test return code
            if not test_name.endswith("/return_code"):
                metricvalue = str(round(float(value), 3)) # 3 digit precision
                dashboard.assign(Metric=test_name, MetricValue=metricvalue)
                db_csv_fd.write(dashboard.csv())

    def parse_results(self, gpu, dist, log_path):
        sk = json.load(open(self.sku_file))
        g = [sk[k].keys() for k in sk.keys()]
        print(f"{gpu} {dist} {sk.keys()} {g}")
        sku_info = json.load(open(self.sku_file))[dist][gpu]
        dashboard: DashBoard = Superbench.dash_board_entry(sku_info)

        db_csv_file = f"{os.path.dirname(log_path)}/{gpu}_{dist}.csv"
        print(f"db_csv_file is {db_csv_file}")
        db_csv_fd = open(db_csv_file, "w")
        db_csv_fd.write(dashboard.header_csv())

        subdirs = [entry for entry in os.listdir(log_path)
                   if os.path.isdir(os.path.join(log_path, entry))]
        for subdir in subdirs:
            result_file = os.path.join(log_path, subdir, "results-summary.jsonl")

            dt = datetime.strptime(subdir, "%Y-%m-%d_%H-%M-%S")
            ts = dt.strftime("%Y-%m-%d %H:%M")
            dashboard.assign(RunTimestamp=ts)
            
            print(f"reading result csv: {result_file}")
            Superbench.write_result(json.load(open(result_file)), dashboard, db_csv_fd)

        db_csv_fd.close()


# TODO: parse args to name the cli parameters.
# "--log-dir <log dir path> --gpu <gpu sku> --dist <distribution>"
# "--skuinfo-json <path to skuinfo.json file> describing vms under test"
# Except for log-dir, these can be extracted from the logs.

import argparse

def parse_args():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Parse command line arguments for GPU and distribution")

    # Add arguments
    parser.add_argument('--log-dir', type=str, required=True, help='Directory where sb results are kept')
    parser.add_argument('--gpu', type=str, required=True, help='Specify the GPU')
    parser.add_argument('--dist', type=str, required=True, help='Specify the distribution')

    # Parse the arguments
    return parser.parse_args()


def main():
    args = parse_args()
    log_dir = args.log_dir.rstrip("/")
    assert os.path.isdir(log_dir)

    dist = args.dist
    gpu = args.gpu
    
    print(f"gpu:{gpu}, dist:{dist}, dirname:{os.path.dirname(log_dir)}")
    sb = Superbench(gpu, dist, log_dir)

main()
