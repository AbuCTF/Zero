"""
Prizes API Routes

Endpoints for viewing and claiming prizes.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, require_verified_participant
from app.database import get_session
from app.models import (
    AuditLog,
    Event,
    Participant,
    Prize,
    PrizeStatus,
    Voucher,
    VoucherPool,
    VoucherStatus,
)
from app.schemas import BaseResponse, PrizeClaimRequest, PrizeResponse

router = APIRouter()


@router.get("", response_model=List[PrizeResponse])
async def list_prizes(
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    List all prizes assigned to the current participant.
    """
    result = await db.execute(
        select(Prize)
        .where(Prize.participant_id == participant.id)
        .order_by(Prize.created_at.desc())
    )
    prizes = result.scalars().all()
    
    return [
        PrizeResponse(
            id=p.id,
            prize_type=p.prize_type,
            prize_data=_filter_prize_data(p),
            status=p.status.value,
            claimed_at=p.claimed_at,
            created_at=p.created_at,
        )
        for p in prizes
    ]


@router.get("/{prize_id}", response_model=PrizeResponse)
async def get_prize(
    prize_id: str,
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """Get a specific prize."""
    result = await db.execute(
        select(Prize).where(
            Prize.id == prize_id,
            Prize.participant_id == participant.id,
        )
    )
    prize = result.scalar_one_or_none()
    
    if not prize:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prize not found",
        )
    
    return PrizeResponse(
        id=prize.id,
        prize_type=prize.prize_type,
        prize_data=_filter_prize_data(prize),
        status=prize.status.value,
        claimed_at=prize.claimed_at,
        created_at=prize.created_at,
    )


@router.post("/{prize_id}/claim", response_model=PrizeResponse)
async def claim_prize(
    prize_id: str,
    request: Request,
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Claim a prize.
    
    For voucher prizes, this reveals the voucher code.
    For certificate prizes, this triggers certificate generation.
    """
    result = await db.execute(
        select(Prize).where(
            Prize.id == prize_id,
            Prize.participant_id == participant.id,
        )
    )
    prize = result.scalar_one_or_none()
    
    if not prize:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prize not found",
        )
    
    if prize.status == PrizeStatus.CLAIMED:
        # Already claimed, just return it
        return PrizeResponse(
            id=prize.id,
            prize_type=prize.prize_type,
            prize_data=_get_full_prize_data(prize),
            status=prize.status.value,
            claimed_at=prize.claimed_at,
            created_at=prize.created_at,
        )
    
    if prize.status == PrizeStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prize has expired",
        )
    
    # Handle voucher prizes
    if prize.prize_type == "voucher":
        voucher_id = prize.prize_data.get("voucher_id")
        if voucher_id:
            result = await db.execute(
                select(Voucher).where(Voucher.id == voucher_id)
            )
            voucher = result.scalar_one_or_none()
            
            if voucher:
                voucher.status = VoucherStatus.CLAIMED
                voucher.claimed_by = participant.id
                voucher.claimed_at = datetime.utcnow()
                
                # Update pool count
                result = await db.execute(
                    select(VoucherPool).where(VoucherPool.id == voucher.pool_id)
                )
                pool = result.scalar_one_or_none()
                if pool:
                    pool.claimed_count += 1
    
    # Mark prize as claimed
    prize.status = PrizeStatus.CLAIMED
    prize.claimed_at = datetime.utcnow()
    
    await db.flush()
    
    # Log claim
    audit_log = AuditLog(
        action="prize.claim",
        participant_id=participant.id,
        actor_type="participant",
        resource_type="prize",
        resource_id=prize.id,
        ip_address=get_client_ip(request),
        metadata={"prize_type": prize.prize_type},
    )
    db.add(audit_log)
    await db.flush()
    
    return PrizeResponse(
        id=prize.id,
        prize_type=prize.prize_type,
        prize_data=_get_full_prize_data(prize),
        status=prize.status.value,
        claimed_at=prize.claimed_at,
        created_at=prize.created_at,
    )


def _filter_prize_data(prize: Prize) -> dict:
    """
    Filter prize data for unclaimed prizes.
    
    Hides sensitive info like voucher codes until claimed.
    """
    if prize.status != PrizeStatus.CLAIMED:
        # Hide sensitive data
        data = dict(prize.prize_data)
        
        if "code" in data:
            data["code"] = "****-****-****"
        
        return data
    
    return _get_full_prize_data(prize)


def _get_full_prize_data(prize: Prize) -> dict:
    """Get full prize data for claimed prizes."""
    return dict(prize.prize_data)
