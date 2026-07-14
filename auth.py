from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError


from database import get_db
from models import User, Farm
from schemas import RegisterRequest, LoginRequest

router = APIRouter(tags=["Authentication"])

# ==========================================================
# PASSWORD HASHING
# ==========================================================

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def hash_password(password: str):
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)


# ==========================================================
# REGISTER
# ==========================================================

@router.post("/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):

    try:

        # --------------------------------------------
        # Check Email
        # --------------------------------------------

        existing_email = (
            db.query(User)
            .filter(User.email == data.user.email)
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        # --------------------------------------------
        # Check Phone
        # --------------------------------------------

        existing_phone = (
            db.query(User)
            .filter(User.phone == data.user.phone)
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=400,
                detail="Phone number already registered"
            )

        # --------------------------------------------
        # Hash Password
        # --------------------------------------------

        hashed_password = hash_password(
            data.user.password
        )

        # --------------------------------------------
        # Create User Object
        # --------------------------------------------

        new_user = User(

            first_name=data.user.first_name,

            last_name=data.user.last_name,

            email=data.user.email,

            phone=data.user.phone,

            password=hashed_password

        )

        # --------------------------------------------
        # Save User
        # --------------------------------------------

        db.add(new_user)

        db.flush()

        # db.flush() generates user.id
        # without committing.

        # --------------------------------------------
        # Create Farm Object
        # --------------------------------------------

        new_farm = Farm(

            user_id=new_user.id,

            farm_name=data.farm.farm_name,

            state=data.farm.state,

            district=data.farm.district,

            farm_size=data.farm.farm_size,

            soil_type=data.farm.soil_type,

            irrigation=data.farm.irrigation,

            crops=data.farm.crops,

            iot_nodes=data.farm.iot_nodes

        )

        db.add(new_farm)

        # --------------------------------------------
        # Commit Both Tables
        # --------------------------------------------

        db.commit()

        return {

            "success": True,

            "message": "Registration Successful"

        }

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:
        db.rollback()

    print("========== REGISTER ERROR ==========")
    import traceback
    traceback.print_exc()
    print("====================================")

    raise
# ==========================================================
# LOGIN
# ==========================================================

@router.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):

    # --------------------------------------------
    # Search User By Email
    # --------------------------------------------

    user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    # --------------------------------------------
    # Email Not Found
    # --------------------------------------------

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User does not exist"
        )

    # --------------------------------------------
    # Verify Password
    # --------------------------------------------

    if not verify_password(
        data.password,
        user.password
    ):

        raise HTTPException(
            status_code=401,
            detail="Incorrect Password"
        )

    # --------------------------------------------
    # Get Farm Details
    # --------------------------------------------

    farm = (
        db.query(Farm)
        .filter(Farm.user_id == user.id)
        .first()
    )

    # --------------------------------------------
    # Login Success
    # --------------------------------------------

    return {

        "success": True,

        "message": "Login Successful",

        "user": {

            "id": user.id,

            "first_name": user.first_name,

            "last_name": user.last_name,

            "email": user.email,

            "phone": user.phone

        },

        "farm": {

    "id": farm.id if farm else None,

    "farm_name": farm.farm_name if farm else None,

    "state": farm.state if farm else None,

    "district": farm.district if farm else None,

    "farm_size": farm.farm_size if farm else None,

    "soil_type": farm.soil_type if farm else None,

    "irrigation": farm.irrigation if farm else None,

    "crops": farm.crops if farm else None,

    "iot_nodes": farm.iot_nodes if farm else None

}

    }


# ==========================================================
# USER PROFILE
# ==========================================================

@router.get("/profile/{user_id}")
def get_profile(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    farm = (
        db.query(Farm)
        .filter(Farm.user_id == user.id)
        .first()
    )

    return {

        "user": {

            "id": user.id,

            "first_name": user.first_name,

            "last_name": user.last_name,

            "email": user.email,

            "phone": user.phone

        },

        "farm": {

            "farm_name": farm.farm_name if farm else None,

            "state": farm.state if farm else None,

            "district": farm.district if farm else None,

            "farm_size": farm.farm_size if farm else None,

            "soil_type": farm.soil_type if farm else None,

            "irrigation": farm.irrigation if farm else None,

            "crops": farm.crops if farm else None,

            "iot_nodes": farm.iot_nodes if farm else None

        }

    }
# ==========================================================
# LOGOUT
# ==========================================================

@router.post("/logout")
def logout():

    return {

        "success": True,

        "message": "Logged Out Successfully"

    }
