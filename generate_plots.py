import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

FILE_DATA = "results/row_data/simulation_results.dat"
OUTPUT_DIR = "results/plots"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 11,
    'lines.linewidth': 2.0,
    'lines.markersize': 5
})

def parse_sf_distribution(sf_str):
    """Transform the string SFs into a list of SFs."""
    try:
        parts = sf_str.split('_')
        # Assuming format SF7_SF8_SF9_SF10_SF11_SF12
        return [int(p) for p in parts[:6]] 
    except:
        return [0]*6


def load_and_process_data(filename):
    """Load and process data, calculating additional metrics."""
    try:
        # Read file handling possible spaces in column names
        df = pd.read_csv(filename, skipinitialspace=True)
        
        # Process SF columns
        sf_cols = ['SF7', 'SF8', 'SF9', 'SF10', 'SF11', 'SF12']
        sf_data = df['SFs'].apply(parse_sf_distribution).tolist()
        df_sf = pd.DataFrame(sf_data, columns=sf_cols)
        df = pd.concat([df, df_sf], axis=1)
        
        # Calculate Successful Packets
        df['Successful_Packets'] = df['sent'] * df['DER2']
        
        # --- METRIC: Energy Efficiency ---
        # Energy consumed per Successful Packet (Joules/Packet)
        # Avoid division by zero
        df['Energy_Efficiency'] = df.apply(
            lambda x: x['Energy'] / x['Successful_Packets'] if x['Successful_Packets'] > 0 else np.nan, 
            axis=1
        )
        
        # Sort by nodes to ensure lines are plotted correctly
        df = df.sort_values(by=['Type', 'nodes'])
        
        return df
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{filename}'. Asegúrate de que esté en la misma carpeta.")
        return None


def plot_metric(df, y_col, title, ylabel, filename, log_scale=False):
    """Función genérica para gráficos de líneas comparativos."""
    plt.figure(figsize=(10, 6))
    
    # Separar datos
    base = df[df['Type'] == 'BASE']
    mod = df[df['Type'] == 'MODIFIED']
    
    plt.plot(base['nodes'], base[y_col], 'o--', label='LoRaWAN Estándar (Base)')
    plt.plot(mod['nodes'], mod[y_col], 's-', label='CR-ADR y Eventos Optimizados')
    
    plt.title(title)
    plt.xlabel('Densidad de Nodos')
    plt.ylabel(ylabel)
    plt.legend()
    
    if log_scale:
        plt.yscale('log')
        
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=300)
    plt.close()
    print(f"Gráfico generado: {filename}")


def density_to_nodes_energy(df):
    # 2. Energía Total vs Densidad
    df_mean = df.groupby(['nodes', 'Type']).mean(numeric_only=True).reset_index()
    plt.figure(figsize=(8, 5))

    df_mean['Type'] = df_mean['Type'].replace({'BASE': 'LoRaWAN Estándar (Base)', 'MODIFIED': 'CR-ADR y Eventos Optimizados'})
    sns.lineplot(data=df_mean, x='nodes', y='Energy', hue='Type', style='Type', markers=True, dashes=False, linewidth=2)
    plt.title('Consumo Energético Total de la Red')
    plt.ylabel('Energía Total (J)')
    plt.xlabel('Número de Nodos')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'comparative_energy_advanced.png'), dpi=300)
    print(" -> Generado: comparative_energy_advanced.png")

    max_nodes = df['nodes'].max()
    subset_sf = df_mean[df_mean['nodes'] == max_nodes].copy()
    sf_cols = [f'SF{i}' for i in range(7, 13)]
    df_sf_melt = subset_sf.melt(id_vars=['Type'], value_vars=sf_cols, var_name='SF', value_name='Count')

    plt.figure(figsize=(8, 5))
    sns.barplot(data=df_sf_melt, x='SF', y='Count', hue='Type', palette='viridis')
    plt.title(f'Distribución de SF (Escenario: {max_nodes} Nodos)')
    plt.ylabel('Cantidad de Nodos (Promedio)')
    plt.xlabel('Factor de Dispersión')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'comparative_sf_distribution.png'), dpi=300)
    print(" -> Generado: comparative_sf_distribution.png")

    df_mean['Pct_Success'] = df_mean['DER2'] * 100
    df_mean['Pct_Collision'] = (df_mean['coll'] / df_mean['sent']) * 100
    df_mean['Pct_Loss_Other'] = 100 - df_mean['Pct_Success'] - df_mean['Pct_Collision']
    
    # Filtrar solo escenario máximo para visualizar desglose
    subset_loss = df_mean[df_mean['nodes'] == max_nodes].set_index('Type')
    
    if not subset_loss.empty:
        plt.figure(figsize=(6, 6))
        
        # Preparar datos para stack
        types = subset_loss.index
        success = subset_loss['Pct_Success']
        coll = subset_loss['Pct_Collision']
        other = subset_loss['Pct_Loss_Other']
        
        # Gráfico
        p1 = plt.bar(types, success, label='Éxito (ACK Recibido)', color='#2ca02c', alpha=0.8)
        p2 = plt.bar(types, coll, bottom=success, label='Colisiones', color='#d62728', alpha=0.8)
        p3 = plt.bar(types, other, bottom=success+coll, label='Pérdida (Ruido/NoACK)', color='#7f7f7f', alpha=0.8)
        
        plt.title(f'Desglose del Destino de Paquetes ({max_nodes} Nodos)')
        plt.ylabel('Porcentaje (%)')
        plt.legend(loc='lower right')
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, 'comparative_packet_loss_breakdown.png'), dpi=300)
        print(" -> Generado: comparative_packet_loss_breakdown.png")


if __name__ == "__main__":
    print("--- Procesando Datos ---")
    df = load_and_process_data(FILE_DATA)
    
    if df is not None:
        # 1. PDR (Reliability)
        plot_metric(df, 'DER2', 'Tasa de Entrega de Paquetes (PDR)', 'PDR (Ratio)', 'pdr_comparative.png')
        
        # 2. Colisiones (Scalability)
        plot_metric(df, 'coll', 'Comparativa de Colisiones', 'Número de Colisiones', 'collisions_comparative.png')
        
        # 3. Eficiencia Energética (Cost/Benefit)
        plot_metric(df, 'Energy_Efficiency', 'Eficiencia Energética (Costo por Paquete Entregado)', 
                   'Joules / Paquete Exitoso', 'energy_efficiency.png')
        
        density_to_nodes_energy(df)
        
        print("\n Completado.")