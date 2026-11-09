import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
import requests

URL_BASE = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/{anio}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CS2032-WebScraping/1.0)"}
NOMBRE_TABLA = "TablaSismosIGP"
CANTIDAD = 10

def obtener_sismos(anio):
    response = requests.get(URL_BASE.format(anio=anio), headers=HEADERS, timeout=20)
    response.raise_for_status()
    datos = response.json()
    return datos if isinstance(datos, list) else datos.get("data", [])

def clave_orden(sismo):
    return sismo.get('createdAt', '')

def lambda_handler(event, context):
    try:
        anio = datetime.now(timezone(timedelta(hours=-5))).year
        sismos = obtener_sismos(anio)

        if len(sismos) < CANTIDAD:
            sismos += obtener_sismos(anio - 1)

        if not sismos:
            return {'statusCode': 404, 'body': 'No se encontraron sismos en la web del IGP'}

        ultimos = sorted(sismos, key=clave_orden, reverse=True)[:CANTIDAD]

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(NOMBRE_TABLA)

        scan = table.scan()
        with table.batch_writer() as batch:
            for each in scan['Items']:
                batch.delete_item(Key={'id': each['id']})

        registros = []
        for i, sismo in enumerate(ultimos, start=1):
            item = json.loads(json.dumps(sismo), parse_float=Decimal)
            item['id'] = str(uuid.uuid4())
            item['#'] = i
            table.put_item(Item=item)
            registros.append(item)

        return {
            'statusCode': 200,
            'cantidad': len(registros),
            'body': json.loads(json.dumps(registros, default=str))
        }

    except requests.RequestException as e:
        return {'statusCode': 502, 'body': f'Error al acceder a la web del IGP: {e}'}
