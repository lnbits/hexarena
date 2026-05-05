# Description: Add your page endpoints here.


from fastapi import APIRouter, Depends
from lnbits.core.views.generic import index, index_public
from lnbits.decorators import check_account_exists
from lnbits.helpers import template_renderer

hexarena_generic_router = APIRouter()


def hexarena_renderer():
    return template_renderer(["hexarena/templates"])


#######################################
##### ADD YOUR PAGE ENDPOINTS HERE ####
#######################################


# Backend admin page
hexarena_generic_router.add_api_route(
    "/", methods=["GET"], endpoint=index, dependencies=[Depends(check_account_exists)]
)


# Frontend shareable page

hexarena_generic_router.add_api_route("/play", methods=["GET"], endpoint=index_public)
hexarena_generic_router.add_api_route("/{game_id}", methods=["GET"], endpoint=index_public)
