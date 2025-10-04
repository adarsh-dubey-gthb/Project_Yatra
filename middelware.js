const User = require("./models/user");

module.exports.isLogged = (req, res, next) => {

    res.locals.curruser = req.user;
    if (!req.isAuthenticated()) {
        req.flash("error", "You must Log-In First");
        return res.redirect("/signIn");
    }
    next();
}

module.exports.saveRedirectUrl = (req, res, next) => {
    if (res.session.redirectUrl) {
        res.locals.redirectUrl = req.session.redirectUrl;
    }
    next();
}