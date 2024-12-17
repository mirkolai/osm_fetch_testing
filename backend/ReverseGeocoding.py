from functools import lru_cache
import json
from typing import Union, List, Tuple, Annotated

import requests
from annotated_types import Len
from pydantic import BaseModel


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
def reverse_geocoding(text: str) -> Tuple[int, str, Union[List[Place] | None]]:
    try:
        headers = {
            'User-Agent': 'United and close',
        }

        response = requests.get(f"https://nominatim.openstreetmap.org/search?format=jsonv2&q={text}", headers=headers)
        print(response.text)
    except:
        return 404, "The requested resource was not found", None

    if response.status_code == 200:
        response = json.loads(response.text)
        places = []
        for row in response:
            place = Place(name=row["display_name"], importance=row["importance"], coordinates=[row["lat"], row["lon"]])
            places.append(place)
        return 200, "OK", places
    else:

        return response.status_code, response.reason, None


if __name__ == "__main__":
    print(reverse_geocoding("torino"))
