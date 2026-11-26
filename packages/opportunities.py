"""Lote revisado para consulta; sem pesquisa ou ações externas."""
import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
router=APIRouter(prefix='/api/opportunities',tags=['opportunities'])
ROOT=Path(__file__).resolve().parents[1]
@router.get('')
async def list_opportunities():
    records=json.loads((ROOT/'apps/api-gateway/opportunities-seed.json').read_text(encoding='utf-8'))
    return {'mode':'review_only','automated_search':False,'outbound_enabled':False,'records':records}
@router.get('/view')
async def view_opportunities():
    return FileResponse(ROOT/'apps/api-gateway/opportunities-view.html',media_type='text/html')
