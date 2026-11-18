require('dotenv').config();
const { createApp } = require('./app');
const secret = process.env.JWT_SECRET;
if (!secret || Buffer.byteLength(secret) < 32) throw new Error('JWT_SECRET must contain at least 32 bytes');
createApp({ secret,
    identityUrl: process.env.IDENTITY_SERVICE_URL || 'http://localhost:3001',
    bookingUrl: process.env.BOOKING_SERVICE_URL || 'http://localhost:8080',
    locationUrl: process.env.LOCATION_SERVICE_URL || 'http://localhost:8000'
}).listen(process.env.PORT || 3000, () => console.log('API Gateway ready'));
