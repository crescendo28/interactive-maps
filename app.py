import os
import logging
from flask import Flask, render_template, request, jsonify

import folium
import folium.features
import pandas as pd
import geopandas as gpd


logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('app.log'),
                        logging.StreamHandler()
                    ])

app = Flask(__name__)


geo_indo = None
available_datasets = {}

def load_data():
    global geo_indo, available_datasets
    
    try:
     
        geojson_path = "indonesia-prov.geojson"
        if not os.path.exists(geojson_path):
            logging.error(f"GeoJSON file not found: {geojson_path}")
            return False

       
        geo_indo = gpd.read_file(geojson_path)
        
        
        data_dir = "data"
        if not os.path.exists(data_dir):
            logging.error(f"Data directory not found: {data_dir}")
            return False

     
        available_datasets.clear()

        
        for filename in os.listdir(data_dir):
            if filename.endswith(".csv"):
                try:
                    dataset_name = os.path.splitext(filename)[0]
                    file_path = os.path.join(data_dir, filename)
                    df = pd.read_csv(file_path)
                    
                   
                    if 'Provinsi' not in df.columns:
                        logging.warning(f"Skipping {filename}: No 'Provinsi' column")
                        continue
                    
                    available_datasets[dataset_name] = df
                    logging.info(f"Loaded dataset: {dataset_name}")
                except Exception as e:
                    logging.error(f"Error loading {filename}: {str(e)}")

        if not available_datasets:
            logging.error("No valid datasets found")
            return False

        return True
    except Exception as e:
        logging.error(f"Data loading failed: {str(e)}")
        return False

def choropleth_map(dataset_name, column_name):
    try:
       
        if dataset_name not in available_datasets:
            logging.error(f"Dataset not found: {dataset_name}")
            return None
        
        data = available_datasets[dataset_name]
        
        if column_name not in data.columns:
            logging.error(f"Column not found: {column_name}")
            return None
        
       
        data['Provinsi'] = data['Provinsi'].str.strip().str.title()
        geo_indo['Propinsi'] = geo_indo['Propinsi'].str.strip().str.title()
        
      
        df_merge = geo_indo.merge(data, how="left", left_on="Propinsi", right_on="Provinsi")
        
        if df_merge.empty:
            logging.error("No data found after merging")
            return None

       
        ina = folium.Map(location=(-2.49607,117.89587), zoom_start=5, tiles="cartodb positron")

        
        try:
            scale = (data[column_name].quantile((0,0.2,0.4,0.6,0.8,1))).tolist()
        except Exception as e:
            logging.warning(f"Scale calculation error: {str(e)}")
            scale = None

       
        choropleth = folium.Choropleth(
            geo_data=geo_indo,
            data=data,
            columns=["Provinsi", column_name],
            key_on="feature.properties.Propinsi",
            threshold_scale=scale,
            fill_color="Blues",
            fill_opacity=0.8,
            line_color="Grey",
            line_opacity=0.3,
            legend_name=f"{column_name} Per Provinsi di Indonesia",
            name=f"{column_name} per Provinsi di Indonesia"
        )
        choropleth.add_to(ina)
        folium.LayerControl().add_to(ina)

      
        style_func = lambda x: {
            "fillColor": "#ffffff", 
            "color": "#000000",
            "fillOpacity": 0.1,
            "weight": 0.1
        }
        
        highlight_func = lambda x: {
            'fillColor': '#000000', 
            'color': '#000000', 
            'fillOpacity': 0.50, 
            'weight': 0.1
        }

        NIL = folium.features.GeoJson(
            data=df_merge,
            style_function=style_func,
            control=False,
            highlight_function=highlight_func,
            tooltip=folium.features.GeoJsonTooltip(
                fields=['Provinsi', column_name],
                aliases=['Provinsi', column_name],
                style=('background-color: white; color:#333333; font-family: arial; font-size:12px; padding: 10px;')
            )
        )
        
        ina.add_child(NIL)
        ina.keep_in_front(NIL)

        return ina
    except Exception as e:
        logging.error(f"Map creation error: {str(e)}")
        return None

@app.route('/')
def index():
   
    if not available_datasets:
        if not load_data():
            return "Error: Could not load data. Check logs for details.", 500

   
    return render_template('index.html', 
                           datasets=list(available_datasets.keys()))

@app.route('/get_columns', methods=['POST'])
def get_columns():
    try:
        dataset_name = request.form.get('dataset')
        if dataset_name in available_datasets:
            columns = [col for col in available_datasets[dataset_name].columns if col != 'Provinsi']
            return jsonify(columns)
        return jsonify([])
    except Exception as e:
        logging.error(f"Get columns error: {str(e)}")
        return jsonify([])

@app.route('/generate_map', methods=['POST'])
def generate_map():
    try:
        dataset_name = request.form.get('dataset')
        column_name = request.form.get('column')

        generated_map = choropleth_map(dataset_name, column_name)

        if generated_map:
            map_html = generated_map.get_root().render()
            return jsonify({
                'success': True,
                'map_html': map_html
            })
        else:
            return jsonify({
                'success': False,
                'error' : 'Error creating map'
            }), 500
    except Exception as e:
        logging.error(f"Map generation error: {str(e)}")
        return jsonify({
            'success' : False,
            'error' : 'An expected error occured'
        }), 500

if __name__ == '__main__':
    load_data()
    app.run(debug=True)
