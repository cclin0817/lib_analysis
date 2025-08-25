#!/usr/bin/env python3
"""
Single Cell OCV Detailed Viewer
Interactive tool to examine OCV ratios for a specific cell
"""

import os
import sys
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import seaborn as sns
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import libertyParser


class SingleCellOCVViewer:
    """Detailed OCV viewer for a single cell"""

    def __init__(self, lib_file, cell_name):
        """
        Initialize viewer for a specific cell

        Args:
            lib_file: Path to liberty file
            cell_name: Name of the cell to analyze
        """
        self.lib_file = lib_file
        self.cell_name = cell_name
        self.cell_data = None
        self.ocv_tables = {}

    def parse_table_values(self, value_str):
        """Parse Liberty table values string to 2D numpy array"""
        if not value_str:
            return None

        clean = value_str.replace('(', '').replace(')', '').replace(',', '')
        rows = []

        for row in clean.split('"'):
            if row.strip() and not re.match(r'^\s+$', row):
                try:
                    rows.append([float(x) for x in row.split()])
                except ValueError:
                    continue

        return np.array(rows) if rows else None

    def load_cell_data(self):
        """Load and parse cell data from liberty file"""
        print(f"Loading cell '{self.cell_name}' from {self.lib_file}...")

        # Parse library with specific cell
        parser = libertyParser.libertyParser(self.lib_file, cellList=[self.cell_name])
        pin_info = parser.getLibPinInfo([self.cell_name])

        if 'cell' not in pin_info or self.cell_name not in pin_info['cell']:
            print(f"Error: Cell '{self.cell_name}' not found in library")
            return False

        self.cell_data = pin_info['cell'][self.cell_name]
        return True

    def extract_ocv_tables(self):
        """Extract all OCV-related tables from the cell"""
        print(f"Extracting OCV tables for cell '{self.cell_name}'...")

        # Categories to extract
        table_categories = {
            'Cell Rise Early': ('cell_rise', 'ocv_sigma_cell_rise_early'),
            'Cell Rise Late': ('cell_rise', 'ocv_sigma_cell_rise_late'),
            'Cell Fall Early': ('cell_fall', 'ocv_sigma_cell_fall_early'),
            'Cell Fall Late': ('cell_fall', 'ocv_sigma_cell_fall_late'),
            'Rise Transition Early': ('rise_transition', 'ocv_sigma_rise_transition_early'),
            'Rise Transition Late': ('rise_transition', 'ocv_sigma_rise_transition_late'),
            'Fall Transition Early': ('fall_transition', 'ocv_sigma_fall_transition_early'),
            'Fall Transition Late': ('fall_transition', 'ocv_sigma_fall_transition_late')
        }

        # Process each pin
        for pin_name, pin_data in self.cell_data.get('pin', {}).items():
            if 'timing' not in pin_data:
                continue

            # Process each timing arc
            for arc_idx, timing_arc in enumerate(pin_data['timing']):
                table_types = timing_arc.get('table_type', {})
                related_pin = timing_arc.get('related_pin', 'N/A')
                arc_key = f"{pin_name}_{related_pin}_{arc_idx}"

                # Extract tables for each category
                for category_name, (mean_table, sigma_table) in table_categories.items():
                    if mean_table in table_types and sigma_table in table_types:
                        mean_values = self.parse_table_values(table_types[mean_table].get('values'))
                        sigma_values = self.parse_table_values(table_types[sigma_table].get('values'))

                        if mean_values is not None and sigma_values is not None:
                            # Calculate OCV ratio
                            with np.errstate(divide='ignore', invalid='ignore'):
                                ratio = np.where(mean_values != 0,
                                              (sigma_values / np.abs(mean_values)) * 100,
                                              0)

                            # Store table data
                            if category_name not in self.ocv_tables:
                                self.ocv_tables[category_name] = []

                            self.ocv_tables[category_name].append({
                                'pin': pin_name,
                                'related_pin': related_pin,
                                'mean_table': mean_values,
                                'sigma_table': sigma_values,
                                'ratio_table': ratio,
                                'arc_key': arc_key
                            })

    def select_worst_case_tables(self):
        """Select worst-case table for each category"""
        worst_case_tables = {}

        for category, tables in self.ocv_tables.items():
            if not tables:
                continue

            # Find table with maximum OCV ratio
            worst_table = None
            max_ratio = 0

            for table_data in tables:
                table_max = np.max(table_data['ratio_table'])
                if table_max > max_ratio:
                    max_ratio = table_max
                    worst_table = table_data

            if worst_table:
                worst_case_tables[category] = worst_table

        return worst_case_tables

    def create_detailed_visualization(self):
        """Create comprehensive visualization with all 8 OCV ratio tables"""
        worst_tables = self.select_worst_case_tables()

        if not worst_tables:
            print("No OCV tables found for this cell")
            return

        # Create figure with 8 subplots (2x4 layout)
        fig = plt.figure(figsize=(24, 12))
        fig.suptitle(f'OCV Analysis for Cell: {self.cell_name}', fontsize=16, fontweight='bold')

        # Define layout
        gs = GridSpec(3, 4, height_ratios=[1, 1, 0.3], hspace=0.3, wspace=0.3)

        # Category order for display
        categories_order = [
            'Cell Rise Early', 'Cell Rise Late', 'Cell Fall Early', 'Cell Fall Late',
            'Rise Transition Early', 'Rise Transition Late', 'Fall Transition Early', 'Fall Transition Late'
        ]

        # Statistics for summary
        summary_stats = []

        # Plot each category
        for idx, category in enumerate(categories_order):
            row = idx // 4
            col = idx % 4
            ax = plt.subplot(gs[row, col])

            if category in worst_tables:
                table_data = worst_tables[category]
                ratio_table = table_data['ratio_table']

                # Create heatmap
                sns.heatmap(ratio_table,
                          annot=True,
                          fmt='.1f',
                          cmap='YlOrRd',
                          vmin=0,
                          vmax=np.percentile(ratio_table, 95),  # Cap at 95th percentile for better contrast
                          cbar_kws={'label': 'OCV Ratio (%)'},
                          ax=ax)

                # Add title with pin info
                title = f"{category}\n"
                title += f"Pin: {table_data['pin']} <- {table_data['related_pin']}\n"
                title += f"Max: {np.max(ratio_table):.1f}%, Mean: {np.mean(ratio_table):.1f}%"
                ax.set_title(title, fontsize=10)
                ax.set_xlabel('Output Load Index', fontsize=9)
                ax.set_ylabel('Input Transition Index', fontsize=9)

                # Collect statistics
                summary_stats.append({
                    'category': category,
                    'max': np.max(ratio_table),
                    'mean': np.mean(ratio_table),
                    'median': np.median(ratio_table),
                    'std': np.std(ratio_table)
                })
            else:
                # No data for this category
                ax.text(0.5, 0.5, 'No Data Available',
                       ha='center', va='center', fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
                ax.set_title(category, fontsize=10)

        # Add summary statistics table
        ax_summary = plt.subplot(gs[2, :])
        ax_summary.axis('tight')
        ax_summary.axis('off')

        # Create summary table
        if summary_stats:
            headers = ['Category', 'Max (%)', 'Mean (%)', 'Median (%)', 'Std Dev (%)']
            table_data = []

            for stat in summary_stats:
                row = [
                    stat['category'].replace(' ', '\n'),  # Break long names
                    f"{stat['max']:.1f}",
                    f"{stat['mean']:.1f}",
                    f"{stat['median']:.1f}",
                    f"{stat['std']:.1f}"
                ]
                table_data.append(row)

            table = ax_summary.table(cellText=table_data,
                                    colLabels=headers,
                                    cellLoc='center',
                                    loc='center',
                                    colWidths=[0.2, 0.1, 0.1, 0.1, 0.1])

            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.5)

            # Color code cells based on values
            for i in range(len(table_data)):
                max_val = float(table_data[i][1])
                if max_val > 15:
                    table[(i+1, 1)].set_facecolor('#ff9999')  # Red for high values
                elif max_val > 10:
                    table[(i+1, 1)].set_facecolor('#ffcc99')  # Orange for moderate

        plt.tight_layout()
        return fig

    def save_detailed_tables(self, output_dir='cell_ocv_details'):
        """Save detailed OCV tables to text files"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        worst_tables = self.select_worst_case_tables()

        # Save each table to a text file
        for category, table_data in worst_tables.items():
            filename = output_path / f"{self.cell_name}_{category.replace(' ', '_')}.txt"

            with open(filename, 'w') as f:
                f.write(f"Cell: {self.cell_name}\n")
                f.write(f"Category: {category}\n")
                f.write(f"Pin: {table_data['pin']} <- {table_data['related_pin']}\n")
                f.write("="*60 + "\n\n")

                f.write("OCV Ratio Table (%):\n")
                f.write("-"*40 + "\n")
                ratio_table = table_data['ratio_table']

                # Write table with proper formatting
                f.write("     ")
                for j in range(ratio_table.shape[1]):
                    f.write(f"   C{j:02d} ")
                f.write("\n")

                for i in range(ratio_table.shape[0]):
                    f.write(f"R{i:02d}: ")
                    for j in range(ratio_table.shape[1]):
                        f.write(f"{ratio_table[i,j]:6.1f} ")
                    f.write("\n")

                f.write("\n" + "="*60 + "\n")
                f.write(f"Statistics:\n")
                f.write(f"  Maximum: {np.max(ratio_table):.2f}%\n")
                f.write(f"  Mean:    {np.mean(ratio_table):.2f}%\n")
                f.write(f"  Median:  {np.median(ratio_table):.2f}%\n")
                f.write(f"  Std Dev: {np.std(ratio_table):.2f}%\n")

                # Find location of maximum
                max_idx = np.unravel_index(np.argmax(ratio_table), ratio_table.shape)
                f.write(f"  Max Location: Row {max_idx[0]}, Col {max_idx[1]}\n")

    def run(self, show_plot=True, save_plot=True, save_tables=True):
        """
        Run the single cell OCV analysis

        Args:
            show_plot: Whether to display the plot
            save_plot: Whether to save the plot to file
            save_tables: Whether to save detailed tables to text files
        """
        # Load cell data
        if not self.load_cell_data():
            return

        # Extract OCV tables
        self.extract_ocv_tables()

        if not self.ocv_tables:
            print(f"No OCV tables found for cell '{self.cell_name}'")
            return

        # Create visualization
        fig = self.create_detailed_visualization()

        # Save plot if requested
        if save_plot:
            output_file = f"{self.cell_name}_ocv_analysis.png"
            fig.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"Saved plot to: {output_file}")

        # Save detailed tables if requested
        if save_tables:
            self.save_detailed_tables()
            print(f"Saved detailed tables to: cell_ocv_details/")

        # Show plot if requested
        if show_plot:
            plt.show()

        # Print summary
        print("\n" + "="*60)
        print(f"OCV Analysis Summary for Cell: {self.cell_name}")
        print("="*60)

        worst_tables = self.select_worst_case_tables()
        for category, table_data in worst_tables.items():
            ratio_table = table_data['ratio_table']
            print(f"\n{category}:")
            print(f"  Pin: {table_data['pin']} <- {table_data['related_pin']}")
            print(f"  Max OCV Ratio: {np.max(ratio_table):.2f}%")
            print(f"  Mean OCV Ratio: {np.mean(ratio_table):.2f}%")


def main():
    """Main entry point for single cell viewer"""
    if len(sys.argv) < 3:
        print("Usage: python single_cell_ocv_viewer.py <library_file> <cell_name>")
        print("\nExample:")
        print("  python single_cell_ocv_viewer.py path/to/library.lib INVX1")
        sys.exit(1)

    lib_file = sys.argv[1]
    cell_name = sys.argv[2]

    # Create viewer and run analysis
    viewer = SingleCellOCVViewer(lib_file, cell_name)
    viewer.run(show_plot=True, save_plot=True, save_tables=True)


if __name__ == '__main__':
    main()
