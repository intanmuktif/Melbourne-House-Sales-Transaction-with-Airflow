'''
=================================================
Milestone 3

Nama  : Intan Mukti Pebriana
Batch : FTDS-019-HCK

Program ini dibuat untuk melakukan automatisasi transform dan load data dari PostgreSQL ke ElasticSearch. 
Adapun dataset yang dipakai adalah dataset mengenai penjualan rumah di Melbourne Australia dari tahun 2016-2017.
=================================================
'''

# Import Libraries
from airflow.models import DAG
from airflow.operators.python import PythonOperator
# from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime
import datetime as dt
from datetime import timedelta
from sqlalchemy import create_engine 
import pandas as pd
import numpy as np

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

# Membuat alur pertama yang dimulai dari memasukkan data ke postgres
def load_csv_to_postgres():
    # Inisialisasi database
    database = "airflow"
    username = "airflow"
    password = "airflow"
    host = "postgres"

    # Membuat URL koneksi untuk PostgreSQL menggunakan format sqlalchemy
    postgres_url = f"postgresql+psycopg2://{username}:{password}@{host}/{database}"

    # Membuat dan membuka engine koneksi ke PostgreSQL
    engine = create_engine(postgres_url)
    conn = engine.connect()

    # Membaca data dari file CSV ke dalam DataFrame
    df = pd.read_csv('/opt/airflow/dags/melb_data.csv')
    
    # Menyimpan DataFrame ke tabel PostgreSQL. Jika tabel sudah ada, tabel akan diganti.
    df.to_sql('table_m3', conn, index=False, if_exists='replace')

    # # Menutup koneksi setelah operasi selesai
    # conn.close()  
    
# Mengambil data dari postgres
def ambil_data():
    # Konfigurasi database
    database = "airflow"
    username = "airflow"
    password = "airflow"
    host = "postgres"

    # Membuat URL koneksi untuk PostgreSQL menggunakan format sqlalchemy
    postgres_url = f"postgresql+psycopg2://{username}:{password}@{host}/{database}"

    # Membuat dan membuka engine koneksi ke PostgreSQL
    engine = create_engine(postgres_url)
    conn = engine.connect()

    # Mengambil data dari tabel PostgreSQL dan menyimpannya ke dalam DataFrame
    df = pd.read_sql_query("select * from table_m3", conn) 

    # Menyimpan DataFrame yang diambil dari database ke file CSV
    df.to_csv('/opt/airflow/dags/data_new.csv', sep=',', index=False)

    # # Menutup koneksi setelah operasi selesai
    # conn.close()  
    

# Melakukan preprocessing pada dataset
def preprocessing(): 
    ''' fungsi untuk membersihkan data
    '''
    # load data
    df = pd.read_csv("/opt/airflow/dags/data_new.csv")

    # Mengubah nama kolom menjadi huruf kecil, menghilangkan angka, dan mengganti spasi dengan underscore
    df.columns = df.columns.str.lower().str.replace(r'\d+', '', regex=True).str.replace(' ', '_')

    # Mengubah nilai None menjadi NaN menggunakan replace
    df.replace({None: np.nan}, inplace=True)

    # Menangani missing value di kolom 'year_built' dengan menggantinya dengan 0
    df['year_built'] = df['year_built'].fillna(0)

    # Hitung median car untuk setiap nilai unik di kolom rooms
    median_car_per_rooms = df.groupby('rooms')['car'].transform('median')

    # Hitung jumlah data untuk setiap nilai rooms
    count_per_rooms = df['rooms'].map(df['rooms'].value_counts())

    # Tentukan median global
    global_median_car = df['car'].median()

    # Isi nilai yang hilang pada kolom car
    df['car'] = df['car'].fillna(
        df.apply(
            lambda row: median_car_per_rooms[row.name] if count_per_rooms[row.name] > 1 else global_median_car,
            axis=1
        )
    )

    # Hitung median building_area untuk setiap nilai unik di kolom rooms
    median_building_area_per_rooms = df.groupby('rooms')['building_area'].transform('median')

    # Hitung jumlah data untuk setiap nilai rooms
    count_per_rooms = df['rooms'].map(df['rooms'].value_counts())

    # Tentukan median global
    global_median_building_area = df['building_area'].median()

    # Isi nilai yang hilang pada kolom building_area
    df['building_area'] = df['building_area'].fillna(
        df.apply(
            lambda row: median_building_area_per_rooms[row.name] if count_per_rooms[row.name] > 1 else global_median_building_area,
            axis=1
        )
    )

    # Mengubah nilai None menjadi NaN menggunakan replace
    df['council_area'] = df['council_area'].replace({None: np.nan})

    # Menghitung nilai 'council_area' pertama yang muncul untuk setiap 'property_count'
    council_area_per_property_count = df.groupby('property_count')['council_area'].first()

    # Mengisi missing value pada kolom 'council_area' dengan nilai berdasarkan 'property_count'
    df['council_area'] = df.apply(
        lambda row: council_area_per_property_count[row['property_count']] 
                    if pd.isna(row['council_area']) 
                    else row['council_area'],
        axis=1
    )

    # Menghapus baris yang memiliki nilai None
    df_cleaned = df.dropna()

    # Mereset indeks DataFrame
    df_cleaned = df_cleaned.reset_index(drop=True)

    # Daftar kolom yang akan diubah menjadi integer
    cols = ['post_code', 'bedroom', 'bathroom', 'car', 'land_size', 
            'building_area', 'year_built','property_count']

    # Looping untuk mengubah tipe data menjadi integer
    for column in cols:
        df_cleaned[column] = pd.to_numeric(df_cleaned[column], errors='coerce').astype('int')

    # Mengubah kolom 'date' menjadi tipe data datetime
    df_cleaned['date'] = pd.to_datetime(df_cleaned['date'], format='%d/%m/%Y')

    # Urutkan DataFrame berdasarkan tahun dan tanggal dari kolom 'date'
    df_cleaned = df_cleaned.sort_values(by=['date'])

    # Ekstrak tahun dan bulan dari kolom 'date' untuk pembuatan 'order_id'
    df_cleaned['order_id'] = df_cleaned.groupby(df_cleaned['date'].dt.year).cumcount() + 1

    # Format 'order_id' dengan tahun dan angka urut
    df_cleaned['order_id'] = df_cleaned['date'].dt.year.astype(str) + '-' + df_cleaned['order_id'].apply(lambda x: f'{x:04d}')

    # Pindahkan 'order_id' ke sebelah kiri tabel
    df_cleaned = df_cleaned[['order_id'] + [col for col in df_cleaned.columns if col != 'order_id']]

    # Reset indeks DataFrame
    df_cleaned = df_cleaned.reset_index(drop=True)


    # save data
    df_cleaned.to_csv('/opt/airflow/dags/P2M3_Intan_data_clean.csv', index=False)



# Fungsi untuk meng-upload data ke Elasticsearch
def upload_to_elasticsearch():
    # Membuat koneksi ke Elasticsearch yang berjalan di alamat dan port tertentu
    es = Elasticsearch("http://elasticsearch:9200")
    
    # Membaca data dari file CSV ke dalam DataFrame pandas
    df = pd.read_csv('/opt/airflow/dags/P2M3_Intan_data_clean.csv')
    
    # Iterasi setiap baris DataFrame
    for i, r in df.iterrows():
        # Mengonversi baris DataFrame menjadi dictionary untuk dikirim ke Elasticsearch
        doc = r.to_dict()  
        # Mengindeks dokumen ke Elasticsearch pada indeks "table_m3" dengan ID yang diatur
        res = es.index(index="table_m3", id=i+1, body=doc)
        # Mencetak respons dari Elasticsearch setelah berhasil mengindeks dokumen
        print(f"Response from Elasticsearch: {res}")
        
        
# Menentukan argumen default untuk DAG seperti owner dan start_date
default_args = {
    'owner': 'intan', 
    'start_date': dt.datetime(2024, 9, 13, 11, 40, 0) - dt.timedelta(hours=7),
}

# Mendefinisikan DAG dengan nama dan parameter tertentu
with DAG(
    "P2M3_Intan_DAG_hck", 
    description='Milestone_3',
    schedule_interval='30 6 * * *', 
    default_args=default_args, 
    catchup=False
) as dag:
 
    # Mendefinisikan tugas untuk memuat data CSV ke PostgreSQL
    load_csv_task = PythonOperator(
        task_id='load_csv_to_postgres',
        python_callable=load_csv_to_postgres) 
    
    # Mendefinisikan tugas untuk mengambil data dari PostgreSQL
    ambil_data_pg = PythonOperator(
        task_id='ambil_data_postgres',
        python_callable=ambil_data) 
    
    # Mendefinisikan tugas untuk melakukan preprocessing data
    edit_data = PythonOperator(
        task_id='edit_data',
        python_callable=preprocessing)

    # Mendefinisikan tugas untuk meng-upload data ke Elasticsearch
    upload_data = PythonOperator(
        task_id='upload_data_elastic',
        python_callable=upload_to_elasticsearch)

 
    # Menetapkan urutan eksekusi tugas
    load_csv_task >> ambil_data_pg >> edit_data >> upload_data



