"""Sites CRUD + connection test."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.site import Site
from app.schemas.site import SiteConnectionTest, SiteCreate, SiteOut, SiteUpdate
from app.services.crypto_service import CryptoService
from app.services.ticimax_service import TicimaxService

router = APIRouter()


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.query(Site).order_by(Site.id).all()


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(payload: SiteCreate, db: Session = Depends(get_db)):
    encrypted = CryptoService.encrypt(payload.uye_kodu)
    site = Site(
        name=payload.name,
        domain=payload.domain,
        uye_kodu_encrypted=encrypted,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site_id: int, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.patch("/{site_id}", response_model=SiteOut)
def update_site(site_id: int, payload: SiteUpdate, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if payload.name is not None:
        site.name = payload.name
    if payload.domain is not None:
        site.domain = payload.domain
    if payload.uye_kodu is not None:
        site.uye_kodu_encrypted = CryptoService.encrypt(payload.uye_kodu)

    db.commit()
    db.refresh(site)
    TicimaxService.invalidate(site.id)
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    db.delete(site)
    db.commit()
    TicimaxService.invalidate(site_id)


@router.post("/{site_id}/test-connection", response_model=SiteConnectionTest)
def test_connection(site_id: int, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    result = TicimaxService.test_connection(site)
    return SiteConnectionTest(**result)
