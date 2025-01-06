from flask import Flask, request, jsonify
from functools import lru_cache
import json
from typing import Union, List, Tuple, Annotated

import requests
from annotated_types import Len
from pydantic import BaseModel

app = Flask(__name__)

# https://nominatim.org/release-docs/latest/admin/Installation/

class Place(BaseModel):
    name: str  # = Field(default=None, examples=["torino"])
    importance: float  # = Field(default=None, examples=[0.6379760396975804])
    coordinates: Annotated[
        list[float], Len(min_length=2, max_length=2)]  # = Field(default=None, examples=[[-19.9160819,0.17]])


class ReverseGeocodingResult(BaseModel):
    status: int  # = Field(default=None, examples=[200])
    message: str  # = Field(default=None, examples=["OK"])
    result: Union[List[Place], None]  # = Field(default=None, examples=[{"name":"Tonga","importance":0.6379760396975804,
    # "coordinates":["-19.9160819","-175.202642"]}])


@lru_cache(maxsize=1000)
def reverse_geocoding(query: str) -> Tuple[int, str, Union[List[Place] | None]]:
    try:
        headers = {'User-Agent': 'United and close'}
        response = requests.get(f"https://nominatim.openstreetmap.org/search?format=jsonv2&q={query}", headers=headers)
    except Exception as e:
        return 500, f"Error: {str(e)}", None

    if response.status_code == 200:
        response_data = json.loads(response.text)
        places = [
            Place(
                name=row["display_name"],
                importance=row.get("importance", 0),
                coordinates=[float(row["lat"]), float(row["lon"])]
            )
            for row in response_data
        ]
        return 200, "OK", places
    else:
        return response.status_code, response.reason, None



if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    print(reverse_geocoding("torino"))
