#!/usr/bin/env python3
"""
List Cells Utility
Quick tool to list all cells in a Liberty file and check for OCV tables
"""

import os
import sys
import re
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import libertyParser


def check_ocv_tables(pin_info, cell_name):
    """Check if a cell has OCV tables"""
    ocv_types = [
        'ocv_sigma_cell_rise_early', 'ocv_sigma_cell_rise_late',
        'ocv_sigma_cell_fall_early', 'ocv_sigma_cell_fall_late',
        'ocv_sigma_rise_transition_early', 'ocv_sigma_rise_transition_late',
        'ocv_sigma_fall_transition_early', 'ocv_sigma_fall_transition_late'
    ]
    
    if 'cell' not in pin_info or cell_name not in pin_info['cell']:
        return False, []
    
    found_ocv_types = set()
    cell_data = pin_info['cell'][cell_name]
    
    for pin_name, pin_data in cell_data.get('pin', {}).items():
        if 'timing' not in pin_data:
            continue
        
        for timing_arc in pin_data['timing']:
            table_types = timing_arc.get('table_type', {})
            for ocv_type in ocv_types:
                if ocv_type in table_types:
                    found_ocv_types.add(ocv_type)
    
    return len(found_ocv_types) > 0, list(found_ocv_types)


def analyze_library(lib_file, filter_pattern=None):
    """
    Analyze a liberty file and list all cells with OCV information
    
    Args:
        lib_file: Path to liberty file
        filter_pattern: Optional regex pattern to filter cells
    """
    print(f"\nAnalyzing library: {lib_file}")
    print("="*60)
    
    # Parse library to get cell list
    print("Parsing library file...")
    parser = libertyParser.libertyParser(lib_file)
    cells = parser.getCellList()
    
    if not cells:
        print("No cells found in library")
        return
    
    print(f"Total cells found: {len(cells)}\n")
    
    # Apply filter if provided
    if filter_pattern:
        pattern = re.compile(filter_pattern, re.IGNORECASE)
        cells = [c for c in cells if pattern.search(c)]
        print(f"Cells matching filter '{filter_pattern}': {len(cells)}\n")
    
    # Categorize cells
    cells_with_ocv = []
    cells_without_ocv = []
    
    print("Checking cells for OCV tables...")
    for i, cell in enumerate(cells):
        # Show progress for large libraries
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(cells)} cells...")
        
        # Get pin info for this cell
        pin_info = parser.getLibPinInfo([cell])
        has_ocv, ocv_types = check_ocv_tables(pin_info, cell)
        
        if has_ocv:
            cells_with_ocv.append((cell, len(ocv_types)))
        else:
            cells_without_ocv.append(cell)
    
    # Display results
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    
    print(f"\nCells with OCV tables: {len(cells_with_ocv)}")
    print(f"Cells without OCV tables: {len(cells_without_ocv)}")
    
    if cells_with_ocv:
        print("\n" + "-"*40)
        print("Cells with OCV Tables (sorted by name):")
        print("-"*40)
        
        # Sort by cell name
        cells_with_ocv.sort(key=lambda x: x[0])
        
        # Group by cell type prefix (e.g., INV, NAND, etc.)
        cell_groups = {}
        for cell, ocv_count in cells_with_ocv:
            # Extract prefix (first continuous letters)
            prefix_match = re.match(r'^([A-Z]+)', cell)
            prefix = prefix_match.group(1) if prefix_match else 'OTHER'
            
            if prefix not in cell_groups:
                cell_groups[prefix] = []
            cell_groups[prefix].append((cell, ocv_count))
        
        # Display grouped cells
        for prefix in sorted(cell_groups.keys()):
            print(f"\n{prefix} cells ({len(cell_groups[prefix])}):")
            for cell, ocv_count in cell_groups[prefix][:10]:  # Show first 10 of each type
                print(f"  - {cell:30s} ({ocv_count} OCV table types)")
            if len(cell_groups[prefix]) > 10:
                print(f"  ... and {len(cell_groups[prefix]) - 10} more {prefix} cells")
    
    if cells_without_ocv and len(cells_without_ocv) <= 20:
        print("\n" + "-"*40)
        print("Cells WITHOUT OCV Tables:")
        print("-"*40)
        for cell in sorted(cells_without_ocv):
            print(f"  - {cell}")
    
    # Export cell list to file
    output_file = Path(lib_file).stem + "_cell_list.txt"
    with open(output_file, 'w') as f:
        f.write(f"Liberty File: {lib_file}\n")
        f.write(f"Total Cells: {len(cells)}\n")
        f.write(f"Cells with OCV: {len(cells_with_ocv)}\n")
        f.write(f"Cells without OCV: {len(cells_without_ocv)}\n")
        f.write("\n" + "="*60 + "\n")
        f.write("CELLS WITH OCV TABLES:\n")
        f.write("="*60 + "\n")
        
        for cell, ocv_count in sorted(cells_with_ocv):
            f.write(f"{cell} ({ocv_count} OCV types)\n")
        
        if cells_without_ocv:
            f.write("\n" + "="*60 + "\n")
            f.write("CELLS WITHOUT OCV TABLES:\n")
            f.write("="*60 + "\n")
            for cell in sorted(cells_without_ocv):
                f.write(f"{cell}\n")
    
    print(f"\nCell list exported to: {output_file}")
    
    # Suggest example cells for analysis
    if cells_with_ocv:
        print("\n" + "="*60)
        print("SUGGESTED CELLS FOR DETAILED ANALYSIS")
        print("="*60)
        
        # Pick diverse cell types
        suggested = []
        for prefix in ['INV', 'NAND', 'NOR', 'BUF', 'DFF', 'MUX']:
            if prefix in cell_groups and cell_groups[prefix]:
                # Pick the one with most OCV tables
                best_cell = max(cell_groups[prefix], key=lambda x: x[1])
                suggested.append(best_cell[0])
        
        if suggested:
            print("\nYou can analyze these cells in detail using:")
            for cell in suggested[:5]:
                print(f"  python single_cell_ocv_viewer.py {lib_file} {cell}")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python list_cells.py <library_file> [filter_pattern]")
        print("\nExamples:")
        print("  python list_cells.py path/to/library.lib")
        print("  python list_cells.py path/to/library.lib INV")
        print("  python list_cells.py path/to/library.lib 'NAND.*X1'")
        sys.exit(1)
    
    lib_file = sys.argv[1]
    filter_pattern = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(lib_file):
        print(f"Error: File '{lib_file}' not found")
        sys.exit(1)
    
    analyze_library(lib_file, filter_pattern)


if __name__ == '__main__':
    main()
