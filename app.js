const express = require("express");
const app = express();
const path = require("path");
const port = 3000;
const cors = require("cors");
const dotenv = require("dotenv");
const axios = require("axios");
const mongoose = require('mongoose');
const ejsmate = require('ejs-mate');
const cookieParser = require("cookie-parser");
const connectFlash = require("connect-flash");
const session = require('express-session');
const flash = require("connect-flash");
const OriginDest = require("./models/origin-destSchema.js");
const wrapAsync = require("./utils/wrapAsync.js");
const ExpressError = require("./utils/expressError.js");
const passport = require("passport");
const LocalStrategy = require("passport-local");
const User = require("./models/user.js");
const { saveRedirectUrl, isLogged } = require("./middelware.js");
dotenv.config();
const MAPBOX_TOKEN = process.env.MAPBOX_TOKEN || process.env.MAP_API_TOKEN;

//------Express-Session------
const expressSession = {
    secret: process.env.EXPRESS_SESSION_KEY,
    resave: false,
    saveUninitialized: true,

};

// --- Python API URLs ---
const PYTHON_API_BASE_URL = 'http://127.0.0.1:5000';
const PYTHON_TRIP_PLAN_URL = `${PYTHON_API_BASE_URL}/get-realtime-trip-plan`;
const PYTHON_STATS_URL = `${PYTHON_API_BASE_URL}/get-system-stats`;





// --- App Setup ---
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.urlencoded({ extended: true }));
app.engine("ejs", ejsmate);
app.use(express.static(path.join(__dirname, "/public")));

//-------Flash --------
app.use(session(expressSession));
app.use(flash());

//-----Authorisation------
app.use(passport.initialize());
app.use(passport.session());

passport.use(new LocalStrategy(User.authenticate()));

passport.serializeUser(User.serializeUser());
passport.deserializeUser(User.deserializeUser());


//flash routers / routes ke upar hi difine karna hai
app.use((req, res, next) => {
    res.locals.success = req.flash("success");
    res.locals.error = req.flash("error");

    next(); //isko na bhulna brna code yhi stuck ho jayega
});

// --- Database Connection ---
main().then(() => {
    console.log("Mongoose is working");
}).catch(err => console.log(err));
async function main() {
    await mongoose.connect('mongodb://127.0.0.1:27017/DlBusDemo');
}

// --- Helper Function: Geocode ---
async function geocode(text) {
    const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(text)}.json`;
    const resp = await axios.get(url, {
        params: { access_token: MAPBOX_TOKEN, limit: 1 }
    });
    if (!resp.data.features || resp.data.features.length === 0) {
        throw new Error(`No geocode result for "${text}"`);
    }
    const feat = resp.data.features[0];
    return { lon: feat.center[0], lat: feat.center[1], place_name: feat.place_name };
}

// --- MAIN PAGE ROUTE (GET) ---
// --- MAIN PAGE ROUTE (GET) ---
app.get("/buses", async (req, res) => {
    try {
        console.log("--- [GET /buses] Fetching dashboard stats... ---");
        const statsResponse = await axios.get(PYTHON_STATS_URL);
        const stats = statsResponse.data;
        console.log("--- [GET /buses] Stats received:", stats);

        res.render("./busses/index.ejs", {
            stats: stats,
            tripPlan: null,
            OriginDest: {},
            mapboxToken: MAPBOX_TOKEN,
            routeGeoJSON: null,
            origin: null,
            dest: null,
            distanceMeters: null,
            durationSeconds: null
        });
    } catch (err) {
        console.error("--- [GET /buses] Error fetching dashboard stats:", err.message);
        res.render("./busses/index.ejs", {
            stats: { active_buses_count: 'N/A', avg_delay_minutes: 'N/A', on_time_percentage: 'N/A', routes_covered_count: 'N/A', last_updated: new Date().toISOString() },
            tripPlan: null,
            OriginDest: {},
            mapboxToken: MAPBOX_TOKEN,
            routeGeoJSON: null,
            origin: null,
            dest: null,
            distanceMeters: null,
            durationSeconds: null
        });
    }
});

// --- TRIP PLANNER ROUTE (POST) ---
app.post("/api/busses/path", async (req, res) => {
    try {
        console.log("\n--- [POST /api/busses/path] Received new trip request ---");
        console.log("1. Raw data from form (req.body):", req.body);

        const startText = req.body?.OriginDest?.start;
        const endText = req.body?.OriginDest?.end;
        if (!startText || !endText) {
            return res.status(400).send("Provide start and end locations");
        }

        const origin = await geocode(startText);
        const dest = await geocode(endText);
        console.log("2. Geocoded Start Location:", origin);
        console.log("   Geocoded End Location:", dest);

        const tripRequest = {
            start_coords: { lat: origin.lat, lon: origin.lon },
            end_coords: { lat: dest.lat, lon: dest.lon }
        };
        console.log("3. Sending this request to Python API:", tripRequest);

        const response = await axios.post(PYTHON_TRIP_PLAN_URL, tripRequest);
        const tripPlan = response.data;
        console.log("4. Received COMPLETE plan from Python API. Final Plan has", Object.keys(tripPlan.final_plan || {}).length, "route(s).");
        // Use JSON.stringify with indentation to see the full structure
        console.log("   Full Python Response:", JSON.stringify(tripPlan, null, 2));


        const statsResponse = await axios.get(PYTHON_STATS_URL);
        const stats = statsResponse.data;
        
        const newPath = new OriginDest(req.body.OriginDest);
        await OriginDest.deleteMany({});
        await newPath.save();
        console.log("5. Saved search to MongoDB.");

        console.log("6. Rendering page with results...");
        res.render("busses/index.ejs", {
            stats: stats,
            tripPlan: tripPlan,
            newPath,
            OriginDest: newPath,
            mapboxToken: MAPBOX_TOKEN,
            origin: origin,
            dest: dest,
            routeGeoJSON: null,
            distanceMeters: null,
            durationSeconds: null
        });

    } catch (err) {
        console.error("--- [POST /api/busses/path] An error occurred:", err.message);
        return res.status(500).send("Error computing route: " + err.message);
    }
});

//------SignUp----------

app.get("/signUp", (req, res) => {
    res.render("./users/signUp.ejs");
});

app.post("/sign-up", wrapAsync(async (req, res) => {
    try {
        let { username, email, password } = req.body;
        const newUser = new User({ username, email });
        const signUpUser = await User.register(newUser, password);
        console.log(signUpUser);

        req.signIn(signUpUser, (err) => {
            if (err) {
                return next(err);
            }
            req.flash("success", "User is Registered Successully");
            res.redirect("/buses")
        })
    } catch (err) {
        req.flash("error", "Username already Exist ");
        res.redirect("/signUp");
    }
}));
//----------signIn Route----------
app.get("/signIn", (req, res) => {
    res.render("./users/signIn.ejs");
});
app.post("/signIn", saveRedirectUrl, passport.authenticate('local', { failureRedirect: '/login', failureFlash: true, }), wrapAsync, ((req, res) => {
    req.flash("success", "You are successfully signIn");
    let redirectUrl = res.locals.redirectUrl || "/buses";
    res.redirect(redirectUrl);
}));



// --- Other routes ---
// Add root route to redirect to /buses
app.get("/", (req, res) => {
    res.redirect("/buses");
});

// Handle 404 errors
app.use((req, res, next) => {
    const err = new ExpressError(404, "Page not found");
    next(err);
});

app.use((err, req, res, next) => {
    let { statusCode = 500, message = "Somthing went Wrong" } = err;
    res.status(statusCode).render("busses/error.ejs", { err });
});

// --- Start the Server ---
app.listen(port, () => {
    console.log(`Server is running on ${port}`);
});