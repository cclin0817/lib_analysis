#!/usr/bin/env python3
#!/usr/bin/env python3

import os
import re
import sys
import numpy as np

sys.path.append(os.path.dirname(os.getcwd()))
import libertyParser


def parse_table_values(value_str):
    """Parse Liberty table values string to 2D list"""
    clean = value_str.replace('(', '').replace(')', '').replace(',', '')
    rows = []
    for row in clean.split('"'):
        if row.strip() and not re.match(r'^\s+$', row):
            rows.append([float(x) for x in row.split()])
    return rows


def parse_index(index_str):
    """Parse Liberty index string to list"""
    clean = index_str.replace('"', '').replace('(', '').replace(')', '').replace(',', '')
    return [float(x) for x in clean.split()]


def main():
    # Parse arguments
    if len(sys.argv) < 3:
        print("Usage: python analysis.py <library_path> <sigma_ratio> [cell_key]")
        sys.exit(1)

    lib_path = sys.argv[1]
    sigma_ratio = float(sys.argv[2])
    cell_key = sys.argv[3] if len(sys.argv) > 3 else None

    # Setup output files
    base = lib_path.replace('/', '_')
    files = {
        'cap_early':       open(f'./scripts/{base}_{sigma_ratio}_sigma_early.cap.tcl', 'w'),
        'cap_late':        open(f'./scripts/{base}_{sigma_ratio}_sigma_late.cap.tcl', 'w'),
        'reset_cap_early': open(f'./scripts/{base}_{sigma_ratio}_sigma_early_ori.cap.tcl', 'w'),
        'reset_cap_late':  open(f'./scripts/{base}_{sigma_ratio}_sigma_late_ori.cap.tcl', 'w'),
    }

    # Skip patterns
    skip_patterns = ['BOUNDARY', 'FILL', 'DCAP', 'TAPCELL', 'BUFTD',
                    'GBUFF', 'LVLHLBUFF', 'LVLLHBUFF', 'PTBUFF', 'GDEL']

    cell_count = 0
    table_count = 0

    # Process each library file
    for lib_file in os.listdir(lib_path):
        if not lib_file.endswith('.lib') or lib_file.startswith('.'):
            continue

        print(f'Parsing lib... {lib_file}')

        # Parse library
        parser = libertyParser.libertyParser(f'{lib_path}/{lib_file}')
        cells = parser.getCellList()
        pin_info = parser.getLibPinInfo(cells)

        scenario = lib_path.replace("lib/", "")
        lib_name = lib_file.replace(".lib", "").replace("hm_lvf_p_", "")

        # Process each cell
        for cell in cells:
            # Skip check
            if any(pattern in cell for pattern in skip_patterns):
                continue
            if cell_key and cell_key not in cell:
                continue
            if 'cell' not in pin_info or cell not in pin_info['cell']:
                continue

            # Store constraints for this cell
            cap_constraints = {'early': {}, 'late': {}, 'ori': {}}

            # Process each pin
            for pin, pin_data in pin_info['cell'][cell].get('pin', {}).items():
                if 'timing' not in pin_data:
                    continue

                # Process each timing arc
                for timing in pin_data['timing']:
                    tables = timing.get('table_type', {})

                    # Check required tables exist
                    required = ['rise_transition', 'fall_transition',
                               'ocv_sigma_rise_transition_early', 'ocv_sigma_fall_transition_early']
                    if not all(t in tables for t in required):
                        continue

                    table_count += 1

                    table_data = {}
                    for table_name in ['rise_transition', 'fall_transition',
                                      'ocv_sigma_rise_transition_early', 'ocv_sigma_fall_transition_early',
                                      'ocv_sigma_rise_transition_late', 'ocv_sigma_fall_transition_late']:
                        if table_name in tables:
                            table_data[table_name] = {
                                'values': parse_table_values(tables[table_name]['values']),
                                'index_1': parse_index(tables[table_name]['index_1']),
                                'index_2': parse_index(tables[table_name]['index_2'])
                            }

                    # Get reference values
                    target_trans = table_data['rise_transition']['index_1'][7]
                    ori_cap_value = table_data['rise_transition']['index_2'][7]

                    # Calculate constraints for each corner
                    for corner in ['early', 'late']:
                        cap_boundary = 8

                        # Check all table positions
                        for i in range(8):
                            for j in range(8):
                                violation = False

                                # Check rise transition
                                rise_key = 'rise_transition'
                                ocv_rise_key = f'ocv_sigma_rise_transition_{corner}'
                                if rise_key in table_data and ocv_rise_key in table_data:
                                    mean_val = table_data[rise_key]['values'][j][i]
                                    ocv_val = table_data[ocv_rise_key]['values'][j][i]
                                    if mean_val * 0.95 + sigma_ratio * ocv_val > target_trans:
                                        violation = True

                                # Check fall transition
                                if not violation:
                                    fall_key = 'fall_transition'
                                    ocv_fall_key = f'ocv_sigma_fall_transition_{corner}'
                                    if fall_key in table_data and ocv_fall_key in table_data:
                                        mean_val = table_data[fall_key]['values'][j][i]
                                        ocv_val = table_data[ocv_fall_key]['values'][j][i]
                                        if mean_val * 0.95 + sigma_ratio * ocv_val > target_trans:
                                            violation = True

                                if violation:
                                    cap_boundary = min(cap_boundary, max(i, j))

                        # Store constraint if found
                        if cap_boundary < 8:
                            cap_value = table_data['fall_transition']['index_2'][cap_boundary - 1]
                            # Keep the most restrictive constraint
                            if pin not in cap_constraints[corner] or cap_value < cap_constraints[corner][pin]:
                                cap_constraints[corner][pin] = cap_value
                                cap_constraints['ori'][pin] = ori_cap_value

            # Write constraints for this cell
            if cap_constraints['early'] or cap_constraints['late']:
                cell_count += 1
                for corner in ['early', 'late']:
                    for pin, cap in cap_constraints[corner].items():
                        pname = f"{lib_name}/{cell}/{pin}"
                        files[f'cap_{corner}'].write(
                            f'set_max_capacitance {cap} -scenarios {scenario} {pname}\n'
                        )
                        files[f'reset_cap_{corner}'].write(
                            f'set_max_capacitance {cap_constraints['ori'][pin]} -scenarios {scenario} {pname}\n'
                        )

    print(f'Cell Number: {cell_count}, Table count: {table_count}')

    # Close all files
    for f in files.values():
        f.close()


if __name__ == '__main__':
    main()
