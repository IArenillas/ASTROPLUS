from datetime import datetime
import pytz
import math
import matplotlib.pyplot as plt
import numpy as np
import swisseph as swe
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from io import BytesIO

app = FastAPI()

# Datos de nacimiento
class BirthData(BaseModel):
    birth_date: str
    birth_time: str
    latitude: float
    longitude: float

@app.post("/calculate_positions/")
def calculate_positions(data: BirthData):
    try:
        # Convertir la hora local a UTC
        birth_datetime_local = datetime.strptime(f"{data.birth_date} {data.birth_time}", "%Y-%m-%d %H:%M")
        local_time_zone = pytz.timezone("Europe/Madrid")
        birth_datetime_utc = local_time_zone.localize(birth_datetime_local).astimezone(pytz.utc)

        # Cálculo del Julian Day para swisseph
        hour_decimal = birth_datetime_utc.hour + birth_datetime_utc.minute / 60
        jd = swe.julday(birth_datetime_utc.year, birth_datetime_utc.month, birth_datetime_utc.day, hour_decimal)

        # Función para calcular el ascendente tropical usando swisseph
        def calculate_tropical_ascendant(jd, latitude, longitude):
            house_system = 'P'  # Sistema de casas Placidus
            asc_mc, cusps = swe.houses(jd, latitude, longitude, house_system.encode())
            return asc_mc[0]  # El ascendente es el primer elemento

        # Calcular el ascendente tropical
        ascendant_tropical = calculate_tropical_ascendant(jd, data.latitude, data.longitude)

        # Calcular el ayanamsa y el ascendente sideral
        ayanamsa = swe.get_ayanamsa(jd)
        ascendant_sidereal = (ascendant_tropical - ayanamsa) % 360

        # Determinar los signos del ascendente
        zodiac_signs = [
            "Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo",
            "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"
        ]

        # Signo y grado para el ascendente tropical
        tropical_sign = zodiac_signs[int(ascendant_tropical // 30)]
        tropical_degree = ascendant_tropical % 30

        # Signo y grado para el ascendente sideral
        sidereal_sign = zodiac_signs[int(ascendant_sidereal // 30)]
        sidereal_degree = ascendant_sidereal % 30

        # Funciones para calcular posiciones planetarias y nodos lunares
        def calculate_approximate_positions():
            try:
                north_node = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]  # Nodo norte (uso de nodo medio)
                south_node = (north_node + 180) % 360  # Nodo sur
                positions = {
                    "\u2609 Sun": 211.57,
                    "\u263D Moon": 88.66,
                    "\u263F Mercury": 193.29,
                    "\u2640 Venus": 165.66,
                    "\u2642 Mars": 91.98,
                    "\u2643 Jupiter": 18.44,
                    "\u2644 Saturn": 122.92,
                    "\u2645 Uranus": 213.06,
                    "\u2646 Neptune": 250.43,
                    "\u2647 Pluto": 190.32,
                    "North Node": north_node,
                    "South Node": south_node
                }
                return positions
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error calculating positions: {e}")

        # Calcular posiciones planetarias aproximadas
        positions = calculate_approximate_positions()

        # Convertir posiciones tropicales a siderales
        def convert_to_sidereal(tropical_positions, ayanamsa):
            sidereal_positions = {}
            for planet, position in tropical_positions.items():
                sidereal_position = position - ayanamsa
                if sidereal_position < 0:
                    sidereal_position += 360  # Asegurarse de que esté en el rango 0-360
                sidereal_positions[planet] = sidereal_position
            return sidereal_positions

        sidereal_positions = convert_to_sidereal(positions, ayanamsa)

        return {
            "ascendant_tropical": {
                "sign": tropical_sign,
                "degree": round(tropical_degree, 2)
            },
            "ascendant_sidereal": {
                "sign": sidereal_sign,
                "degree": round(sidereal_degree, 2)
            },
            "planetary_positions_tropical": positions,
            "planetary_positions_sidereal": sidereal_positions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@app.post("/calculate_dasha/")
def calculate_dasha(data: BirthData):
    try:
        # Esta función implementará los cálculos de Dashas
        birth_datetime_local = datetime.strptime(f"{data.birth_date} {data.birth_time}", "%Y-%m-%d %H:%M")
        local_time_zone = pytz.timezone("Europe/Madrid")
        birth_datetime_utc = local_time_zone.localize(birth_datetime_local).astimezone(pytz.utc)
        jd = swe.julday(birth_datetime_utc.year, birth_datetime_utc.month, birth_datetime_utc.day)
        ayanamsa = swe.get_ayanamsa(jd)

        # Cálculo simplificado de Vimshottari Dasha para ejemplo
        total_dasha_years = 120  # Total años en Vimshottari
        moon_long = swe.calc_ut(jd, swe.MOON)[0][0] - ayanamsa
        if moon_long < 0:
            moon_long += 360
        dasha_start = (moon_long % 27) / 27 * total_dasha_years

        return {
            "vimshottari_dasha": {
                "start": round(dasha_start, 2),
                "total_years": total_dasha_years
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

@app.get("/generate_chart/")
def generate_chart():
    try:
        # Genera un gráfico visual basado en posiciones calculadas
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.set_aspect("equal")

        # Dibujar círculo
        circle = plt.Circle((0, 0), 1.0, color="black", fill=False)
        ax.add_artist(circle)

        # Dibujar divisiones de casas
        for i in range(12):
            angle = i * 30 * math.pi / 180
            x = math.cos(angle)
            y = math.sin(angle)
            ax.plot([0, x], [0, y], color="gray")

        # Dibujar signos zodiacales
        zodiac = [
            "\u2648", "\u2649", "\u264A", "\u264B", "\u264C", "\u264D", 
            "\u264E", "\u264F", "\u2650", "\u2651", "\u2652", "\u2653"
        ]
        for i, sign in enumerate(zodiac):
            angle = (i * 30 + 15) * math.pi / 180
            x = math.cos(angle) * 1.2
            y = math.sin(angle) * 1.2
            ax.text(x, y, sign, fontsize=10, ha="center", va="center")

        # Guardar como archivo descargable
        buf = BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
