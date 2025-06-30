// Restaurant Voice Assistant Script

// Define menu categories and common responses
const CATEGORIES = ['Appetizers', 'Main Course', 'Desserts', 'Beverages', 'Specials'];

const RESPONSES = {
  greeting: "Welcome to our restaurant! How may I assist you today?",
  menu: "I can tell you about our menu items, take your order, or help you make a reservation. What would you like to do?",
  notUnderstood: "I apologize, I didn't quite catch that. Could you please repeat?",
  orderConfirmation: "I'll help you place your order. What would you like to order?",
  reservationStart: "I'll help you make a reservation. What date would you like to reserve?",
  goodbye: "Thank you for calling! Have a great day!"
};

// Main conversation flow
conversation.on('start', async () => {
  await conversation.say(RESPONSES.greeting);
  await conversation.say(RESPONSES.menu);
});

// Handle menu inquiries
conversation.on('menu inquiry', async () => {
  const category = conversation.get('category');
  if (category && CATEGORIES.includes(category)) {
    const menuItems = await fetchMenuItems(category);
    await conversation.say(`Here are our ${category}: ${formatMenuItems(menuItems)}`);
  } else {
    await conversation.say("Our menu categories include Appetizers, Main Course, Desserts, Beverages, and Specials. Which would you like to hear about?");
  }
});

// Handle orders
conversation.on('place order', async () => {
  await conversation.say(RESPONSES.orderConfirmation);
  const order = {
    items: [],
    total: 0,
    phone: conversation.get('phone'),
    timestamp: new Date().toISOString(),
    status: 'pending'
  };
  
  while (true) {
    const item = await conversation.ask("What would you like to order? Say 'done' when finished.");
    if (item.toLowerCase() === 'done') break;
    
    const menuItem = await findMenuItem(item);
    if (menuItem) {
      order.items.push(menuItem);
      order.total += menuItem.price;
      await conversation.say(`Added ${menuItem.name} to your order. Total is now $${order.total.toFixed(2)}`);
    } else {
      await conversation.say("I'm sorry, I couldn't find that item. Please try again.");
    }
  }
  
  if (order.items.length > 0) {
    await saveOrder(order);
    await conversation.say(`Your order has been placed! Total is $${order.total.toFixed(2)}. We'll start preparing it right away.`);
  }
});

// Handle reservations
conversation.on('make reservation', async () => {
  await conversation.say(RESPONSES.reservationStart);
  
  const reservation = {
    phone: conversation.get('phone'),
    timestamp: new Date().toISOString(),
    status: 'pending'
  };

  // Get date
  const date = await conversation.ask("What date would you like to reserve? (For example, 'tomorrow' or 'next Friday')");
  reservation.date = parseDate(date);

  // Get time
  const time = await conversation.ask("What time would you like to reserve?");
  reservation.time = parseTime(time);

  // Get party size
  const partySize = await conversation.ask("How many people in your party?");
  reservation.party_size = parseInt(partySize);

  // Confirm reservation
  await saveReservation(reservation);
  await conversation.say(`Perfect! I've made a reservation for ${reservation.party_size} people on ${reservation.date} at ${reservation.time}. We look forward to seeing you!`);
});

// Handle FAQs
conversation.on('faq inquiry', async () => {
  const question = conversation.get('question');
  const faq = await findFAQ(question);
  
  if (faq) {
    await conversation.say(faq.answer);
  } else {
    await conversation.say("I'm sorry, I don't have specific information about that. Would you like me to connect you with a staff member?");
  }
});

// Handle goodbyes
conversation.on('goodbye', async () => {
  await conversation.say(RESPONSES.goodbye);
});

// Helper functions
async function fetchMenuItems(category) {
  // Implement API call to your backend
  const response = await fetch(`${process.env.BACKEND_URL}/api/menu-items?category=${category}`);
  return await response.json();
}

function formatMenuItems(items) {
  return items.map(item => `${item.name} for $${item.price.toFixed(2)}`).join(', ');
}

async function findMenuItem(itemName) {
  // Implement fuzzy search for menu items
  const response = await fetch(`${process.env.BACKEND_URL}/api/menu-items`);
  const items = await response.json();
  return items.find(item => item.name.toLowerCase().includes(itemName.toLowerCase()));
}

async function saveOrder(order) {
  // Implement API call to save order
  await fetch(`${process.env.BACKEND_URL}/api/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(order)
  });
}

async function saveReservation(reservation) {
  // Implement API call to save reservation
  await fetch(`${process.env.BACKEND_URL}/api/reservations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reservation)
  });
}

async function findFAQ(question) {
  // Implement API call to search FAQs
  const response = await fetch(`${process.env.BACKEND_URL}/api/faqs`);
  const faqs = await response.json();
  return faqs.find(faq => 
    faq.question.toLowerCase().includes(question.toLowerCase())
  );
}

function parseDate(dateStr) {
  // Implement date parsing logic
  // This should handle various date formats and relative dates like "tomorrow", "next Friday", etc.
  return new Date(dateStr).toISOString().split('T')[0];
}

function parseTime(timeStr) {
  // Implement time parsing logic
  // This should handle various time formats like "6pm", "18:00", etc.
  return timeStr;
}

// Error handling
conversation.on('error', async (error) => {
  console.error('Conversation error:', error);
  await conversation.say("I apologize, but I'm having trouble processing your request. Would you like me to connect you with a staff member?");
});

// Fallback for unhandled intents
conversation.on('unhandled', async () => {
  await conversation.say(RESPONSES.notUnderstood);
}); 