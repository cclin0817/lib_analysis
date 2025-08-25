#!/usr/bin/env python3
"""
OCV (On-Chip Variation) Analysis Tool
Analyzes OCV sigma ratios across all cells in Liberty files
"""

import os
import sys
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path for libertyParser import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import libertyParser


class OCVAnalyzer:
    """Main class for OCV analysis of Liberty files"""

    def __init__(self, lib_path, output_dir='ocv_analysis_output'):
        """
        Initialize OCV Analyzer

        Args:
            lib_path: Path to liberty file or directory containing liberty files
            output_dir: Directory for output files
        """
        self.lib_path = lib_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Store analysis results
        self.cell_results = {}
        self.summary_stats = {}

        # Analysis categories
        self.analysis_types = {
            'cell_delay': {
                'cell_rise': ['ocv_sigma_cell_rise_early', 'ocv_sigma_cell_rise_late'],
                'cell_fall': ['ocv_sigma_cell_fall_early', 'ocv_sigma_cell_fall_late']
            },
            'transition': {
                'rise_transition': ['ocv_sigma_rise_transition_early', 'ocv_sigma_rise_transition_late'],
                'fall_transition': ['ocv_sigma_fall_transition_early', 'ocv_sigma_fall_transition_late']
            }
        }

    def parse_table_values(self, value_str):
        """Parse Liberty table values string to 2D numpy array"""
        if not value_str:
            return None

        # Clean up the string
        clean = value_str.replace('(', '').replace(')', '').replace(',', '')
        rows = []

        # Split by quotes and parse each row
        for row in clean.split('"'):
            if row.strip() and not re.match(r'^\s+$', row):
                try:
                    rows.append([float(x) for x in row.split()])
                except ValueError:
                    continue

        return np.array(rows) if rows else None

    def parse_index(self, index_str):
        """Parse Liberty index string to list"""
        if not index_str:
            return None

        clean = index_str.replace('"', '').replace('(', '').replace(')', '').replace(',', '')
        try:
            return [float(x) for x in clean.split()]
        except ValueError:
            return None

    def calculate_ocv_ratio(self, mean_table, sigma_table):
        """
        Calculate OCV ratio for each point in the table

        Args:
            mean_table: 2D array of mean values
            sigma_table: 2D array of sigma values

        Returns:
            2D array of ratios (percentage)
        """
        if mean_table is None or sigma_table is None:
            return None

        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = np.where(mean_table != 0,
                            (sigma_table / np.abs(mean_table)) * 100,
                            0)
        return ratio

    def analyze_timing_arc(self, timing_data):
        """
        Analyze a single timing arc for OCV ratios

        Returns:
            Dictionary with OCV analysis for this arc
        """
        arc_results = {}
        table_types = timing_data.get('table_type', {})

        # Process cell delay OCV ratios
        for mean_type, sigma_types in self.analysis_types['cell_delay'].items():
            if mean_type in table_types:
                mean_values = self.parse_table_values(table_types[mean_type].get('values'))

                for sigma_type in sigma_types:
                    corner = 'early' if 'early' in sigma_type else 'late'
                    key = f"{mean_type}_{corner}"

                    if sigma_type in table_types and mean_values is not None:
                        sigma_values = self.parse_table_values(table_types[sigma_type].get('values'))
                        ratio_table = self.calculate_ocv_ratio(mean_values, sigma_values)

                        if ratio_table is not None:
                            arc_results[key] = {
                                'ratio_table': ratio_table,
                                'max_ratio': np.max(ratio_table),
                                'mean_ratio': np.mean(ratio_table),
                                'median_ratio': np.median(ratio_table),
                                'std_ratio': np.std(ratio_table)
                            }

        # Process transition OCV ratios
        for mean_type, sigma_types in self.analysis_types['transition'].items():
            if mean_type in table_types:
                mean_values = self.parse_table_values(table_types[mean_type].get('values'))

                for sigma_type in sigma_types:
                    corner = 'early' if 'early' in sigma_type else 'late'
                    key = f"{mean_type}_{corner}"

                    if sigma_type in table_types and mean_values is not None:
                        sigma_values = self.parse_table_values(table_types[sigma_type].get('values'))
                        ratio_table = self.calculate_ocv_ratio(mean_values, sigma_values)

                        if ratio_table is not None:
                            arc_results[key] = {
                                'ratio_table': ratio_table,
                                'max_ratio': np.max(ratio_table),
                                'mean_ratio': np.mean(ratio_table),
                                'median_ratio': np.median(ratio_table),
                                'std_ratio': np.std(ratio_table)
                            }

        return arc_results

    def analyze_cell(self, cell_name, cell_data):
        """
        Analyze all pins and timing arcs for a cell
        Select worst case when multiple arcs exist
        """
        cell_analysis = {}

        # Initialize results for all 8 analysis types
        for category in ['cell_rise_early', 'cell_rise_late', 'cell_fall_early', 'cell_fall_late',
                        'rise_transition_early', 'rise_transition_late',
                        'fall_transition_early', 'fall_transition_late']:
            cell_analysis[category] = None

        # Process each pin
        for pin_name, pin_data in cell_data.get('pin', {}).items():
            if 'timing' not in pin_data:
                continue

            # Analyze each timing arc
            for timing_arc in pin_data['timing']:
                arc_results = self.analyze_timing_arc(timing_arc)

                # Keep worst case (highest max ratio) for each analysis type
                for key, results in arc_results.items():
                    if results and (cell_analysis[key] is None or
                                  results['max_ratio'] > cell_analysis[key]['max_ratio']):
                        cell_analysis[key] = results
                        cell_analysis[key]['pin'] = pin_name
                        cell_analysis[key]['related_pin'] = timing_arc.get('related_pin', 'N/A')

        return cell_analysis

    def process_library(self, lib_file):
        """Process a single liberty file"""
        print(f"\nProcessing library: {lib_file}")

        # Parse library
        parser = libertyParser.libertyParser(lib_file)
        cells = parser.getCellList()
        pin_info = parser.getLibPinInfo(cells)

        if 'cell' not in pin_info:
            print(f"No cells found in {lib_file}")
            return

        # Process each cell
        for cell_name in cells:
            if cell_name not in pin_info['cell']:
                continue

            # Analyze cell
            cell_results = self.analyze_cell(cell_name, pin_info['cell'][cell_name])

            # Store results
            self.cell_results[cell_name] = cell_results

        print(f"Processed {len(cells)} cells")

    def generate_summary_statistics(self):
        """Generate summary statistics across all cells"""
        summary = {
            'total_cells': len(self.cell_results),
            'analysis_types': {}
        }

        # Collect statistics for each analysis type
        for analysis_type in ['cell_rise_early', 'cell_rise_late', 'cell_fall_early', 'cell_fall_late',
                             'rise_transition_early', 'rise_transition_late',
                             'fall_transition_early', 'fall_transition_late']:

            max_ratios = []
            mean_ratios = []

            for cell_name, cell_data in self.cell_results.items():
                if cell_data[analysis_type] is not None:
                    max_ratios.append(cell_data[analysis_type]['max_ratio'])
                    mean_ratios.append(cell_data[analysis_type]['mean_ratio'])

            if max_ratios:
                summary['analysis_types'][analysis_type] = {
                    'cells_with_data': len(max_ratios),
                    'max_ratio_overall': max(max_ratios),
                    'mean_max_ratio': np.mean(max_ratios),
                    'median_max_ratio': np.median(max_ratios),
                    'percentile_95': np.percentile(max_ratios, 95),
                    'mean_of_means': np.mean(mean_ratios)
                }

        self.summary_stats = summary
        return summary

    def identify_worst_cells(self, threshold=10.0, top_n=20):
        """
        Identify cells with highest OCV ratios

        Args:
            threshold: OCV ratio threshold for flagging (percentage)
            top_n: Number of worst cells to report
        """
        worst_cells = []

        for cell_name, cell_data in self.cell_results.items():
            worst_ratio = 0
            worst_type = None

            for analysis_type, results in cell_data.items():
                if results and results['max_ratio'] > worst_ratio:
                    worst_ratio = results['max_ratio']
                    worst_type = analysis_type

            if worst_ratio > threshold:
                worst_cells.append({
                    'cell': cell_name,
                    'worst_ratio': worst_ratio,
                    'worst_type': worst_type,
                    'pin': cell_data[worst_type]['pin'] if cell_data[worst_type] else 'N/A'
                })

        # Sort by worst ratio
        worst_cells.sort(key=lambda x: x['worst_ratio'], reverse=True)

        return worst_cells[:top_n]

    def create_heatmap(self, ratio_table, title, filename):
        """Create heatmap visualization for 8x8 ratio table"""
        if ratio_table is None:
            return

        plt.figure(figsize=(10, 8))
        sns.heatmap(ratio_table, annot=True, fmt='.1f', cmap='YlOrRd',
                   cbar_kws={'label': 'OCV Ratio (%)'})
        plt.title(title)
        plt.xlabel('Output Load Index')
        plt.ylabel('Input Transition Index')
        plt.tight_layout()
        plt.savefig(filename, dpi=100)
        plt.close()

    def generate_cell_report(self, cell_name, max_cells_detail=10):
        """Generate detailed report for a specific cell"""
        if cell_name not in self.cell_results:
            return

        cell_data = self.cell_results[cell_name]
        cell_dir = self.output_dir / f"cell_{cell_name}"
        cell_dir.mkdir(exist_ok=True)

        # Generate heatmaps for each analysis type
        for analysis_type, results in cell_data.items():
            if results and results['ratio_table'] is not None:
                self.create_heatmap(
                    results['ratio_table'],
                    f"{cell_name} - {analysis_type.replace('_', ' ').title()} OCV Ratio",
                    cell_dir / f"{analysis_type}.png"
                )

    def generate_summary_plots(self):
        """Generate summary visualization plots"""

        # 1. Distribution of max OCV ratios across all cells
        fig, axes = plt.subplots(2, 4, figsize=(20, 10))
        fig.suptitle('OCV Ratio Distribution Across All Cells', fontsize=16)

        analysis_types = ['cell_rise_early', 'cell_rise_late', 'cell_fall_early', 'cell_fall_late',
                         'rise_transition_early', 'rise_transition_late',
                         'fall_transition_early', 'fall_transition_late']

        for idx, analysis_type in enumerate(analysis_types):
            ax = axes[idx // 4, idx % 4]

            max_ratios = []
            for cell_data in self.cell_results.values():
                if cell_data[analysis_type] is not None:
                    max_ratios.append(cell_data[analysis_type]['max_ratio'])

            if max_ratios:
                ax.hist(max_ratios, bins=30, edgecolor='black', alpha=0.7)
                ax.axvline(np.mean(max_ratios), color='red', linestyle='--', label=f'Mean: {np.mean(max_ratios):.1f}%')
                ax.set_xlabel('Max OCV Ratio (%)')
                ax.set_ylabel('Number of Cells')
                ax.set_title(analysis_type.replace('_', ' ').title())
                ax.legend()
                ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'ocv_distribution_summary.png', dpi=150)
        plt.close()

        # 2. Comparison of Early vs Late corners
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Cell delays
        early_cell = []
        late_cell = []
        for cell_data in self.cell_results.values():
            for timing_type in ['cell_rise', 'cell_fall']:
                if cell_data[f'{timing_type}_early'] is not None:
                    early_cell.append(cell_data[f'{timing_type}_early']['max_ratio'])
                if cell_data[f'{timing_type}_late'] is not None:
                    late_cell.append(cell_data[f'{timing_type}_late']['max_ratio'])

        axes[0].boxplot([early_cell, late_cell], labels=['Early', 'Late'])
        axes[0].set_ylabel('Max OCV Ratio (%)')
        axes[0].set_title('Cell Delay OCV Comparison')
        axes[0].grid(True, alpha=0.3)

        # Transitions
        early_trans = []
        late_trans = []
        for cell_data in self.cell_results.values():
            for timing_type in ['rise_transition', 'fall_transition']:
                if cell_data[f'{timing_type}_early'] is not None:
                    early_trans.append(cell_data[f'{timing_type}_early']['max_ratio'])
                if cell_data[f'{timing_type}_late'] is not None:
                    late_trans.append(cell_data[f'{timing_type}_late']['max_ratio'])

        axes[1].boxplot([early_trans, late_trans], labels=['Early', 'Late'])
        axes[1].set_ylabel('Max OCV Ratio (%)')
        axes[1].set_title('Transition Time OCV Comparison')
        axes[1].grid(True, alpha=0.3)

        plt.suptitle('Early vs Late Corner OCV Analysis', fontsize=14)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'early_vs_late_comparison.png', dpi=150)
        plt.close()

    def generate_html_report(self):
        """Generate interactive HTML report"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OCV Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; margin-top: 30px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .warning {{ color: red; font-weight: bold; }}
                .summary-box {{ background-color: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
                .stat-item {{ background-color: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <h1>OCV (On-Chip Variation) Analysis Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <div class="summary-box">
                <h2>Executive Summary</h2>
                <div class="stat-grid">
                    <div class="stat-item">
                        <strong>Total Cells Analyzed:</strong> {self.summary_stats['total_cells']}
                    </div>
        """

        # Add key statistics
        for analysis_type, stats in self.summary_stats['analysis_types'].items():
            if stats:
                html_content += f"""
                    <div class="stat-item">
                        <strong>{analysis_type.replace('_', ' ').title()}:</strong><br>
                        Max: {stats['max_ratio_overall']:.1f}%<br>
                        95th percentile: {stats['percentile_95']:.1f}%
                    </div>
                """

        html_content += """
                </div>
            </div>

            <h2>Worst Cells (OCV Ratio > 10%)</h2>
            <table>
                <tr>
                    <th>Rank</th>
                    <th>Cell Name</th>
                    <th>Worst OCV Ratio (%)</th>
                    <th>Analysis Type</th>
                    <th>Pin</th>
                </tr>
        """

        # Add worst cells table
        worst_cells = self.identify_worst_cells()
        for idx, cell_info in enumerate(worst_cells, 1):
            warning_class = 'class="warning"' if cell_info['worst_ratio'] > 15 else ''
            html_content += f"""
                <tr>
                    <td>{idx}</td>
                    <td>{cell_info['cell']}</td>
                    <td {warning_class}>{cell_info['worst_ratio']:.2f}</td>
                    <td>{cell_info['worst_type'].replace('_', ' ').title()}</td>
                    <td>{cell_info['pin']}</td>
                </tr>
            """

        html_content += """
            </table>

            <h2>OCV Distribution Analysis</h2>
            <img src="ocv_distribution_summary.png" alt="OCV Distribution">

            <h2>Early vs Late Corner Comparison</h2>
            <img src="early_vs_late_comparison.png" alt="Early vs Late Comparison">

            <h2>Detailed Cell Analysis</h2>
            <p>For detailed 8x8 heatmaps of specific cells, check the individual cell folders in the output directory.</p>

        </body>
        </html>
        """

        # Write HTML file
        with open(self.output_dir / 'ocv_analysis_report.html', 'w') as f:
            f.write(html_content)

    def export_to_csv(self):
        """Export analysis results to CSV for further processing"""
        rows = []

        for cell_name, cell_data in self.cell_results.items():
            row = {'cell': cell_name}

            for analysis_type, results in cell_data.items():
                if results:
                    row[f'{analysis_type}_max'] = results['max_ratio']
                    row[f'{analysis_type}_mean'] = results['mean_ratio']
                    row[f'{analysis_type}_median'] = results['median_ratio']
                else:
                    row[f'{analysis_type}_max'] = None
                    row[f'{analysis_type}_mean'] = None
                    row[f'{analysis_type}_median'] = None

            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_csv(self.output_dir / 'ocv_analysis_results.csv', index=False)

        return df

    def run_analysis(self):
        """Main analysis pipeline"""
        print("=" * 60)
        print("Starting OCV Analysis")
        print("=" * 60)

        # Process library files
        if os.path.isfile(self.lib_path):
            self.process_library(self.lib_path)
        elif os.path.isdir(self.lib_path):
            for lib_file in Path(self.lib_path).glob('*.lib'):
                self.process_library(str(lib_file))
        else:
            print(f"Error: {self.lib_path} is not a valid file or directory")
            return

        if not self.cell_results:
            print("No cells found to analyze")
            return

        print(f"\nTotal cells analyzed: {len(self.cell_results)}")

        # Generate statistics
        print("\nGenerating summary statistics...")
        self.generate_summary_statistics()

        # Generate visualizations
        print("Creating visualizations...")
        self.generate_summary_plots()

        # Generate detailed reports for worst cells
        print("Generating detailed cell reports...")
        worst_cells = self.identify_worst_cells(threshold=10.0, top_n=5)
        for cell_info in worst_cells:
            self.generate_cell_report(cell_info['cell'])

        # Export results
        print("Exporting results to CSV...")
        df = self.export_to_csv()

        # Generate HTML report
        print("Generating HTML report...")
        self.generate_html_report()

        # Print summary to console
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print(f"\nResults saved to: {self.output_dir}")
        print(f"- HTML Report: ocv_analysis_report.html")
        print(f"- CSV Data: ocv_analysis_results.csv")
        print(f"- Visualizations: *.png files")

        # Print top worst cells
        print("\nTop 5 Worst Cells (Highest OCV Ratios):")
        print("-" * 40)
        for idx, cell_info in enumerate(worst_cells[:5], 1):
            print(f"{idx}. {cell_info['cell']}: {cell_info['worst_ratio']:.2f}% "
                  f"({cell_info['worst_type'].replace('_', ' ')})")

        return df


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python ocv_analysis.py <library_path> [output_dir]")
        print("  library_path: Path to .lib file or directory containing .lib files")
        print("  output_dir: Optional output directory (default: ocv_analysis_output)")
        sys.exit(1)

    lib_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'ocv_analysis_output'

    # Run analysis
    analyzer = OCVAnalyzer(lib_path, output_dir)
    analyzer.run_analysis()


if __name__ == '__main__':
    main()

