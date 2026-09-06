const User = require("../models/User");
const { success, error } = require("../utils/apiResponse");

const getProfile = async (req, res) => {
  return success(res, req.user.toProfileJSON());
};

const updateProfile = async (req, res, next) => {
  try {
    const user = req.user;
    const {
      name,
      email,
      role,
      college,
      course,
      year,
      about,
      photo,
      phone,
    } = req.body;

    if (name !== undefined) {
      if (!String(name).trim()) {
        return error(res, "Please enter your full name.", 400);
      }

      user.fullName = String(name).trim();
    }

    if (email !== undefined) {
      const nextEmail = String(email).trim().toLowerCase();

      if (!/^\S+@\S+\.\S+$/.test(nextEmail)) {
        return error(res, "Please enter a valid email address.", 400);
      }

      const taken = await User.findOne({
        email: nextEmail,
        _id: { $ne: user._id },
      });

      if (taken) {
        return error(res, "An account with this email already exists.", 409);
      }

      user.email = nextEmail;
    }

    if (role !== undefined) {
      user.displayRole = String(role);
    }

    if (college !== undefined) user.college = String(college);
    if (course !== undefined) user.course = String(course);
    if (year !== undefined) user.year = String(year);
    if (about !== undefined) user.about = String(about);
    if (photo !== undefined) user.photo = String(photo);
    if (phone !== undefined) user.phone = String(phone);

    await user.save();

    return success(res, user.toProfileJSON(), "Profile updated successfully.");
  } catch (err) {
    next(err);
  }
};

module.exports = {
  getProfile,
  updateProfile,
};
