#!/usr/bin/env python3

import os
import re
import sys

os.environ["PYTHONUNBUFFERED"]="1"
cwd = os.getcwd()
upperLevelPath = os.path.dirname(cwd)
sys.path.append(upperLevelPath)
import libertyParser
import numpy as np
from scipy.interpolate import interp2d
import matplotlib.pyplot as plt


def getInterpolate2DFunction(table):
    index_1 = str21DArr(table['index_1'])
    index_2 = str21DArr(table['index_2'])
    values = str22DArr(table['values'])
    return interp2d(index_2, index_1, values, kind='cubic'), index_1, index_2

def str2list(value_str):
    return value_str.replace(" ", "").replace("\"", "").replace("(", "").replace(")", "").split(",")

def str22DArr(value_str):
    new_value = value_str.replace("(", "").replace(")", "").replace(",", "")
    row = new_value.split("\"")
    twod_array = []
    for row_str in row:
        match = re.search(r'^\s+$', row_str)
        if match:
            continue
        else:
            values_str = row_str.split(" ")
            new_values_list = []
            for value_str in values_str:
                value = float(value_str)
                new_values_list.append(value)
            twod_array.append(new_values_list)

    np_2d_arr = np.array(twod_array)
    return np_2d_arr

def str21DArr(value_str):
    new_value = value_str.replace("\"", "").replace("(", "").replace(")", "").replace(",", "").split(" ")
    new_values_list = []
    for str in new_value:
        value = float(str)
        new_values_list.append(value)

    np_1d_arr = np.array(new_values_list)
    return np_1d_arr

def main():

    # Configurable variables
    analysis_libs = './libs/m40c_UD_lvt_libs'
    analysis_libs = sys.argv[1]
    #sigma_ratio = 3
    sigma_ratio = float(sys.argv[2])
    cell_key = None
    #cell_key = sys.argv[3]
    cell_num = 0
    table_size = 8


    capfname_early          = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_early.cap.tcl'
    capfname_late           = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_late.cap.tcl'
    transfname_early        = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_early.trans.tcl'
    transfname_late         = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_late.trans.tcl'
    reset_capfname_early    = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_early_ori.cap.tcl'
    reset_capfname_late     = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_late_ori.cap.tcl'
    reset_transfname_early  = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_early_ori.trans.tcl'
    reset_transfname_late   = './scripts/' + analysis_libs.replace('/', '_') + '_' + str(sigma_ratio) + '_' + 'sigma_late_ori.trans.tcl'
    capofp_early            = open(capfname_early, 'w')
    capofp_late             = open(capfname_late, 'w')
    #transofp_early          = open(transfname_early, 'w')
    #transofp_late           = open(transfname_late, 'w')
    reset_capofp_early      = open(reset_capfname_early, 'w')
    reset_capofp_late       = open(reset_capfname_late, 'w')
    #reset_transofp_early    = open(reset_transfname_early, 'w')
    #reset_transofp_late     = open(reset_transfname_late, 'w')

    table_count = 0

    #analyze_cell_path = '/tmp1/cfchenzh/VIOLATED'
    #analyze_cell_list = []
    #with open(analyze_cell_path, 'r') as analyze_cell_file:
    #    for line in analyze_cell_file:
    #        analyze_cell_list.append(line.strip())

    if False:
        ifp = open('m25c_lvt', 'r')
        print("Generate new ./libs folder")
        if os.path.exists('./libs'):
            os.system('rm -rf ./libs')
        os.mkdir('libs')

        for line in ifp.readlines():
            line = line.rstrip('\n')
            cmd = 'cp ' + line + ' ./libs'
            os.system(cmd)
            filestr = line.split('/')
            cmd = 'gunzip -f ./libs/' + filestr[-1]
            os.system(cmd)

    for libFile in os.listdir(analysis_libs):
        libFile = libFile.rstrip('\n')
        if 'lib' not in libFile: continue
        if libFile[0] == '.': continue

        libPath = analysis_libs + '/' + libFile
        myLibertyParser = libertyParser.libertyParser(libPath)
        libCellList = myLibertyParser.getCellList()
        libPinDic = myLibertyParser.getLibPinInfo(libCellList)
        scenario = analysis_libs.replace("lib/", "")
        libName = libFile.replace(".lib", "").replace("hm_lvf_p_", "")

        print('Parsing lib...', libName, scenario)

        for cell in libCellList:
            if 'BOUNDARY' in cell or 'FILL' in cell or 'DCAP' in cell or 'TAPCELL' in cell: continue
            if 'BUFTD' in cell: continue
            if cell_key != None and cell_key not in cell: continue
            if 'cell' not in libPinDic: continue
            #print('Parsing cell...', cell)
            input_trans_dict_early = {}
            input_trans_dict_late = {}
            input_ori_trans_dict = {}
            for pin in libPinDic['cell'][cell]['pin']:
                if 'timing' not in libPinDic['cell'][cell]['pin'][pin]: continue
                cap_constraint_boundary_early = 8
                cap_constraint_boundary_late = 8
                for timing_info in libPinDic['cell'][cell]['pin'][pin]['timing']:
                    #print("==================================================================================================================================")
                    #print(cell, "related_pin", timing_info['related_pin'], "timing_sense", timing_info['timing_sense'], "timing_type", timing_info['timing_type'], "when", timing_info['when'])
                    #print(cell, "related_pin", timing_info['related_pin'], "timing_sense", timing_info['timing_sense'], "timing_type", timing_info['timing_type'])
                    #print("==================================================================================================================================")
                    rise_transition_f = None
                    fall_transition_f = None
                    ocv_sigma_rise_transition_early_f = None
                    ocv_sigma_fall_transition_early_f = None
                    ocv_sigma_rise_transition_late_f = None
                    ocv_sigma_fall_transition_late_f = None
                    cell_rise_f = None
                    cell_fall_f = None
                    ocv_sigma_cell_rise_early_f = None
                    ocv_sigma_cell_fall_early_f = None
                    ocv_sigma_cell_rise_late_f = None
                    ocv_sigma_cell_fall_late_f = None

                    # interpolate.interp2d(x, y, z)
                    # x = [0,1,2];  y = [0,3]; z = [[1,2,3], [4,5,6]]
                    # x can specify the column coordinates and y the row coordinates
                    for key in timing_info['table_type']:
                        if 'rise_transition' == key:
                            rise_transition_f, rise_transition_index_1, rise_transition_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'fall_transition' == key:
                            fall_transition_f, fall_transition_index_1, fall_transition_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_rise_transition_early' == key:
                            ocv_sigma_rise_transition_early_f, ocv_sigma_rise_transition_early_index_1, ocv_sigma_rise_transition_early_index_2 =getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_fall_transition_early' == key:
                            ocv_sigma_fall_transition_early_f, ocv_sigma_fall_transition_early_index_1, ocv_sigma_fall_transition_early_index_2  = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_rise_transition_late' == key:
                            ocv_sigma_rise_transition_late_f, ocv_sigma_rise_transition_late_index_1, ocv_sigma_rise_transition_late_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_fall_transition_late' == key:
                            ocv_sigma_fall_transition_late_f, ocv_sigma_fall_transition_late_index_1, ocv_sigma_fall_transition_late_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'cell_rise' == key:
                            cell_rise_f, cell_rise_index_1, cell_rise_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'cell_fall' == key:
                            cell_fall_f, cell_fall_index_1, cell_fall_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_cell_rise_early' == key:
                            ocv_sigma_cell_rise_early_f, ocv_sigma_cell_rise_early_index_1, ocv_sigma_cell_rise_early_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_cell_fall_early' == key:
                            ocv_sigma_cell_fall_early_f, ocv_sigma_cell_fall_early_index_1, ocv_sigma_cell_fall_early_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_cell_rise_late' == key:
                            ocv_sigma_cell_rise_late_f, ocv_sigma_cell_rise_late_index_1, ocv_sigma_cell_rise_late_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                        elif 'ocv_sigma_cell_fall_late' == key:
                            ocv_sigma_cell_fall_late_f, ocv_sigma_cell_fall_late_index_1, ocv_sigma_cell_fall_late_index_2 = getInterpolate2DFunction(timing_info['table_type'][key])
                    #print(cell_rise_index_1.size, cell_fall_index_1.size, ocv_sigma_cell_rise_early_index_1.size, ocv_sigma_cell_rise_late_index_1.size)
                    #print(ocv_sigma_cell_rise_early_f)

                    if rise_transition_f == None or fall_transition_f == None or ocv_sigma_rise_transition_early_f == None or ocv_sigma_fall_transition_early_f == None: continue
                    if 'GBUFF' in cell:         continue
                    if 'LVLHLBUFF' in cell:     continue
                    if 'LVLLHBUFF' in cell:     continue
                    if 'PTBUFF' in cell:        continue
                    if 'GDEL' in cell:          continue
                    #if 'CK' in cell:            continue

                    input_pin = timing_info['related_pin']
                    trans_constraint_boundary_early = 8
                    trans_constraint_boundary_late = 8
                    ori_trans_value = rise_transition_index_1[7]
                    ori_cap_value = rise_transition_index_2[7]
                    target_trasns = rise_transition_index_1[7]

                    for i in range(table_size):
                        for j in range(table_size):
                            update_early = False
                            mean_value = float(rise_transition_f(rise_transition_index_2[i], rise_transition_index_1[j]))
                            ocv_value = float(ocv_sigma_rise_transition_early_f(ocv_sigma_rise_transition_early_index_2[i], ocv_sigma_rise_transition_early_index_1[j]))
                            if mean_value*0.95 + sigma_ratio*ocv_value > target_trasns: update_early = True
                            mean_value = float(fall_transition_f(fall_transition_index_2[i], fall_transition_index_1[j]))
                            ocv_value = float(ocv_sigma_fall_transition_early_f(ocv_sigma_fall_transition_early_index_2[i], ocv_sigma_fall_transition_early_index_1[i]))
                            if mean_value*0.95 + sigma_ratio*ocv_value > target_trasns: update_early = True

                            if update_early:
                                if max(i, j) < trans_constraint_boundary_early:
                                    trans_constraint_boundary_early = max(i, j)
                                    trans_constraint_early = fall_transition_index_1[trans_constraint_boundary_early-1]
                                if max(i, j) < cap_constraint_boundary_early:
                                    cap_constraint_boundary_early = max(i, j)
                                    cap_constraint_early = fall_transition_index_2[trans_constraint_boundary_early-1]

                            update_late = False
                            mean_value = float(rise_transition_f(rise_transition_index_2[i], rise_transition_index_1[j]))
                            ocv_value = float(ocv_sigma_rise_transition_late_f(ocv_sigma_rise_transition_late_index_2[i], ocv_sigma_rise_transition_late_index_1[j]))
                            if mean_value*0.95 + sigma_ratio*ocv_value > target_trasns: update_late = True
                            mean_value = float(fall_transition_f(fall_transition_index_2[i], fall_transition_index_1[j]))
                            ocv_value = float(ocv_sigma_fall_transition_late_f(ocv_sigma_fall_transition_late_index_2[i], ocv_sigma_fall_transition_late_index_1[i]))
                            if mean_value*0.95 + sigma_ratio*ocv_value > target_trasns: update_late = True

                            if update_late:
                                if max(i, j) < trans_constraint_boundary_late:
                                    trans_constraint_boundary_late = max(i, j)
                                    trans_constraint_late = fall_transition_index_1[trans_constraint_boundary_late-1]
                                if max(i, j) < cap_constraint_boundary_late:
                                    cap_constraint_boundary_late = max(i, j)
                                    cap_constraint_late = fall_transition_index_2[trans_constraint_boundary_late-1]

                    if trans_constraint_boundary_early != 8:
                        if input_pin in input_trans_dict_early:
                            if trans_constraint_early < input_trans_dict_early[input_pin]:
                                input_trans_dict_early[input_pin] = trans_constraint_early
                        else:
                            input_trans_dict_early[input_pin] = trans_constraint_early
                            input_ori_trans_dict[input_pin] = ori_trans_value

                    if trans_constraint_boundary_late != 8:
                        if input_pin in input_trans_dict_late:
                            if trans_constraint_late < input_trans_dict_late[input_pin]:
                                input_trans_dict_late[input_pin] = trans_constraint_late
                        else:
                            input_trans_dict_late[input_pin] = trans_constraint_late
                            input_ori_trans_dict[input_pin] = ori_trans_value

                    table_count = table_count + 1

                if cap_constraint_boundary_early != 8:
                    pname = cell + '/' + pin
                    #print('set_max_capacitance', cap_constraint_early, pname, file = capofp_early)
                    #print('set_max_capacitance', ori_cap_value, pname, file = reset_capofp_early)
                    print('set_max_capacitance', cap_constraint_early, '-scenarios', scenario, libName+'/'+pname, file = capofp_early)
                    print('set_max_capacitance', ori_cap_value, '-scenarios', scenario, libName+'/'+pname, file = reset_capofp_early)

                if cap_constraint_boundary_late != 8:
                    pname = cell + '/' + pin
                    #print('set_max_capacitance', cap_constraint_late, pname, file = capofp_late)
                    #print('set_max_capacitance', ori_cap_value, pname, file = reset_capofp_late)
                    print('set_max_capacitance', cap_constraint_late, '-scenarios', scenario, libName+'/'+pname, file = capofp_late)
                    print('set_max_capacitance', ori_cap_value, '-scenarios', scenario, libName+'/'+pname, file = reset_capofp_late)

            #for key, value in input_trans_dict_early.items():
            #    pname = cell + '/' + key.replace("\"", "")
            #    print('set_max_transition', value, pname, file = transofp_early)
            #for key, value in input_ori_trans_dict.items():
            #    pname = cell + '/' + key.replace("\"", "")
            #    print('set_max_transition', value, pname, file = reset_transofp_early)

            #for key, value in input_trans_dict_late.items():
            #    pname = cell + '/' + key.replace("\"", "")
            #    print('set_max_transition', value, pname, file = transofp_late)
            #for key, value in input_ori_trans_dict.items():
            #    pname = cell + '/' + key.replace("\"", "")
            #    print('set_max_transition', value, pname, file = reset_transofp_late)


                    #foreach timing table (when !A)
                #foreach pin
            cell_num = cell_num + 1
            #foreach cell
        #foreach library


    print('Cell Number:', cell_num, 'Table count:', table_count)

if __name__ == '__main__':
    main()


