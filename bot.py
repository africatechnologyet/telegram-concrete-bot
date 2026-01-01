import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO

# Conversation states
(CUSTOMER, LOCATION_INPUT, GRADES, PRICE, QUANTITY, EXTRAS, CONFIRM) = range(7)

# Concrete grades
GRADES_LIST = ['C-15', 'C-20', 'C-25', 'C-30', 'C-35', 'C-37', 'C-40', 'C-45', 'C-50']

# Extra services
EXTRAS_LIST = ['Elephant pump', 'Vibrator', 'Skip', 'None']

# Admin user IDs
ADMIN_IDS = [5613539602]

# Data persistence
DATA_FILE = 'bot_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {'quote_counter': 100, 'quotes': {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

bot_data = load_data()

def generate_pdf(pi_data):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1a3a6b'), spaceAfter=8, alignment=TA_CENTER, fontName='Helvetica-Bold')
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#666666'), alignment=TA_LEFT)
    
    # Header with company info and logo
    company_info = """
    <b>CoBuilt Solutions</b><br/>
    Addis Ababa, Ethiopia<br/>
    Phone: +251911246502<br/>
    +251911246820<br/>
    Email: CoBuilt@CoBuilt.com<br/>
    Web: www.CoBuilt.com
    """
    
    # Try to add logo in top right corner
    try:
        logo = Image('logo.png', width=1*inch, height=1*inch)
        logo.hAlign = 'RIGHT'
        
        # Create table to position company info and logo side by side
        header_table = Table([[Paragraph(company_info, header_style), logo]], colWidths=[4*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        elements.append(header_table)
    except:
        # If logo not found, just add company info
        elements.append(Paragraph(company_info, header_style))
    
    elements.append(Spacer(1, 6))
    
    # Add horizontal line after header
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a3a6b'), spaceAfter=6))
    
    elements.append(Paragraph("CONCRETE QUOTE", title_style))
    
    # Add horizontal line after title
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceBefore=2, spaceAfter=6))
    
    date_quote = f"<para align=right><b>Date:</b> {datetime.now().strftime('%b %d, %Y')}<br/><b>Quote No:</b> {pi_data['quote_number']}</para>"
    elements.append(Paragraph(date_quote, styles['Normal']))
    elements.append(Spacer(1, 6))
    
    # Calculate total quantity
    total_quantity = sum(pi_data['quantity'][g] for g in pi_data['grades'])
    
    customer_data = [
        ['Company:', pi_data['customer'], 'Additional service:', pi_data['extras']],
        ['Location:', pi_data['location'], 'Payment terms:', '100% advance'],
        ['Quantity:', f"{total_quantity:,.2f}m³", 'Validity of quote:', 'Valid for 3 days'],
        ['Concrete Grade:', ', '.join(pi_data['grades']), '', '']
    ]
    
    customer_table = Table(customer_data, colWidths=[1.3*inch, 2*inch, 1.6*inch, 2*inch])
    customer_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(customer_table)
    elements.append(Spacer(1, 8))
    
    # Calculate how many grades - adjust table accordingly
    num_grades = len(pi_data['grades'])
    
    table_data = [['No.', 'Description', 'Grade', 'Quantity', 'Price', 'Total Price']]
    total_amount = 0
    for idx, grade in enumerate(pi_data['grades'], 1):
        unit_price = pi_data['unit_price'][grade]
        quantity = pi_data['quantity'][grade]
        line_total = unit_price * quantity
        total_amount += line_total
        table_data.append([str(idx), 'Concrete OPC', grade, f"{quantity:,.2f}m³", f"{unit_price:,.2f}", f"{line_total:,.2f}"])
    
    # Add subtotal row
    table_data.append(['', '', '', '', 'Subtotal:', f"{total_amount:,.2f}"])
    
    # Calculate VAT (15%)
    vat_amount = total_amount * 0.15
    table_data.append(['', '', '', '', 'VAT (15%):', f"{vat_amount:,.2f}"])
    
    # Calculate Grand Total
    grand_total = total_amount + vat_amount
    table_data.append(['', '', '', '', 'Grand Total:', f"{grand_total:,.2f}"])
    
    pricing_table = Table(table_data, colWidths=[0.4*inch, 2.3*inch, 0.7*inch, 0.9*inch, 1.1*inch, 1.4*inch])
    pricing_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d2691e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -4), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 1), (-1, -4), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -4), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -4), 7),
        ('GRID', (0, 0), (-1, -4), 0.5, colors.HexColor('#999999')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.beige, colors.white]),
        # Subtotal row styling
        ('SPAN', (0, -3), (3, -3)),
        ('ALIGN', (4, -3), (-1, -3), 'RIGHT'),
        ('FONTNAME', (4, -3), (-1, -3), 'Helvetica-Bold'),
        ('FONTSIZE', (4, -3), (-1, -3), 8),
        ('LINEABOVE', (0, -3), (-1, -3), 1, colors.HexColor('#999999')),
        # VAT row styling
        ('SPAN', (0, -2), (3, -2)),
        ('ALIGN', (4, -2), (-1, -2), 'RIGHT'),
        ('FONTNAME', (4, -2), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (4, -2), (-1, -2), 7),
        # Grand Total row styling
        ('SPAN', (0, -1), (3, -1)),
        ('ALIGN', (4, -1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (4, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (4, -1), (-1, -1), 9),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#d2691e')),
        ('BACKGROUND', (4, -1), (-1, -1), colors.HexColor('#f5f5dc')),
    ]))
    elements.append(pricing_table)
    elements.append(Spacer(1, 6))
    
    # Add horizontal line before notes
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=4))
    
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=6, textColor=colors.HexColor('#666666'))
    vat_notice = "<para align=left textColor=#666666><i>Note: VAT (15%) has been included in the Grand Total above.</i></para>"
    elements.append(Paragraph(vat_notice, note_style))
    
    discount_notice = "<para align=left textColor=#999999>- As the order volume increases, we can extend a discount accordingly.</para>"
    elements.append(Paragraph(discount_notice, note_style))
    elements.append(Spacer(1, 5))
    
    # Add horizontal line before terms
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=4))
    
    terms_style = ParagraphStyle('Terms', parent=styles['Normal'], fontSize=7)
    terms_title = "<para align=left><b>Terms &amp; Conditions</b></para>"
    elements.append(Paragraph(terms_title, terms_style))
    elements.append(Spacer(1, 3))
    
    terms = """
    • Delivery Schedule: Within 7–10 working days from confirmation.<br/>
    • Payment Terms: 100% advance.<br/>
    • Validity: This quote is valid for 3 days from the date of issue.<br/>
    • Exclusions: Does not include site preparation, road access issues, or waiting time beyond 1 hour per truck.
    """
    elements.append(Paragraph(terms, terms_style))
    elements.append(Spacer(1, 5))
    
    # Add horizontal line before contact info
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=4))
    
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=7)
    footer_contact = """
    <para align=left><b>For any clarifications, please contact:</b><br/>
    Biruk Endale<br/>
    Chief Operation Officer<br/>
    CoBuilt Solutions<br/>
    +251911246502<br/>
    +251911246520
    </para>
    """
    elements.append(Paragraph(footer_contact, contact_style))
    elements.append(Spacer(1, 3))
    
    try:
        # Signature with "Approved By:" text - maintaining aspect ratio from uploaded image
        signature = Image('signature.png', width=3*inch, height=1.75*inch)
        
        approved_by_style = ParagraphStyle('ApprovedBy', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT)
        approved_by_text = Paragraph("<b>Approved By:</b>", approved_by_style)
        
        # Create table with signature and text below it
        sig_table = Table([[signature], [approved_by_text]], colWidths=[3*inch])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
            ('ALIGN', (0, 1), (0, 1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (0, 0), 0),
            ('TOPPADDING', (0, 1), (0, 1), 2),
        ]))
        sig_table.hAlign = 'RIGHT'
        elements.append(sig_table)
    except Exception as e:
        print(f"Could not add signature: {e}")
    
    elements.append(Spacer(1, 3))
    
    # Add final horizontal line before company footer
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a3a6b'), spaceAfter=3))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7)
    company_footer = "<para align=left><b>A branch of SSara Group</b></para>"
    elements.append(Paragraph(company_footer, footer_style))
    
    pdf.build(elements)
    buffer.seek(0)
    return buffer

# ---- Handlers ----

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Welcome to CoBuilt Solutions PI Bot, {user.first_name}!\n\n"
        f"Commands:\n"
        f"/createpi - Create a new Price Quote\n"
        f"/myquotes - View your quotes\n"
        f"/cancel - Cancel operation\n"
        f"/help - Show help"
    )

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📖 *How to use this bot:*\n1️⃣ /createpi\n2️⃣ Follow prompts\n3️⃣ Add extras\n4️⃣ Delivery location\n5️⃣ Review & confirm\n6️⃣ Admin approval\n7️⃣ Download PDF",
        parse_mode='Markdown'
    )

async def create_pi(update: Update, context: CallbackContext):
    context.user_data.clear()
    context.user_data['pi_data'] = {
        'user_id': update.effective_user.id,
        'username': update.effective_user.username or update.effective_user.first_name,
        'created_at': datetime.now().isoformat()
    }
    keyboard = [['❌ Cancel']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("👤 Enter customer/company name:", reply_markup=reply_markup)
    return CUSTOMER

async def customer_name(update: Update, context: CallbackContext):
    if update.message.text == '❌ Cancel':
        return await cancel(update, context)
    
    context.user_data['pi_data']['customer'] = update.message.text
    keyboard = [['⬅️ Back', '❌ Cancel']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("📍 Enter delivery location:", reply_markup=reply_markup)
    return LOCATION_INPUT

async def location_input(update: Update, context: CallbackContext):
    if update.message.text == '❌ Cancel':
        return await cancel(update, context)
    
    if update.message.text == '⬅️ Back':
        keyboard = [['❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("👤 Enter customer/company name:", reply_markup=reply_markup)
        return CUSTOMER
    
    context.user_data['pi_data']['location'] = update.message.text.strip()
    keyboard = [GRADES_LIST[i:i+4] for i in range(0, len(GRADES_LIST), 4)]
    keyboard.append(['⬅️ Back', '❌ Cancel'])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "🧱 Select concrete grades (comma separated):\n\n"
        "Examples:\n"
        "• Single grade: C-25\n"
        "• Multiple grades: C-25, C-30, C-35\n\n"
        "Available grades: " + ", ".join(GRADES_LIST),
        reply_markup=reply_markup
    )
    return GRADES

async def quantity_input(update: Update, context: CallbackContext):
    keyboard = [GRADES_LIST[i:i+4] for i in range(0, len(GRADES_LIST), 4)]
    keyboard.append(['⬅️ Back', '❌ Cancel'])
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("🧱 Select concrete grades (comma separated):", reply_markup=reply_markup)
    return GRADES

async def grades(update: Update, context: CallbackContext):
    if update.message.text == '❌ Cancel':
        return await cancel(update, context)
    
    if update.message.text == '⬅️ Back':
        keyboard = [['⬅️ Back', '❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("📍 Enter delivery location:", reply_markup=reply_markup)
        return LOCATION_INPUT
    
    grades_input = update.message.text.replace(' ', '')
    grades = [g.strip().upper() for g in grades_input.split(',') if g.strip()]
    
    # Validate grades
    valid_grades = []
    invalid_grades = []
    for grade in grades:
        if grade in GRADES_LIST:
            if grade not in valid_grades:  # Avoid duplicates
                valid_grades.append(grade)
        else:
            invalid_grades.append(grade)
    
    if invalid_grades:
        keyboard = [GRADES_LIST[i:i+4] for i in range(0, len(GRADES_LIST), 4)]
        keyboard.append(['⬅️ Back', '❌ Cancel'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            f"❌ Invalid grades: {', '.join(invalid_grades)}\n\n"
            f"Please select from: {', '.join(GRADES_LIST)}\n"
            f"Enter grades again (comma separated):",
            reply_markup=reply_markup
        )
        return GRADES
    
    if not valid_grades:
        keyboard = [GRADES_LIST[i:i+4] for i in range(0, len(GRADES_LIST), 4)]
        keyboard.append(['⬅️ Back', '❌ Cancel'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("❌ Enter at least one grade.", reply_markup=reply_markup)
        return GRADES
    
    context.user_data['pi_data']['grades'] = valid_grades
    context.user_data['pi_data']['unit_price'] = {}
    context.user_data['pi_data']['quantity'] = {}
    context.user_data['current_grade_index'] = 0

    grade = valid_grades[0]
    keyboard = [['⬅️ Back', '❌ Cancel']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"💵 Grade: {grade}\nEnter price per m³:", reply_markup=reply_markup)
    return PRICE

async def price(update: Update, context: CallbackContext):
    if update.message.text == '❌ Cancel':
        return await cancel(update, context)
    
    if update.message.text == '⬅️ Back':
        # Go back to grades selection
        if context.user_data['current_grade_index'] == 0:
            keyboard = [GRADES_LIST[i:i+4] for i in range(0, len(GRADES_LIST), 4)]
            keyboard.append(['⬅️ Back', '❌ Cancel'])
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                "🧱 Select concrete grades (comma separated):\n\n"
                "Examples:\n"
                "• Single grade: C-25\n"
                "• Multiple grades: C-25, C-30, C-35\n\n"
                "Available grades: " + ", ".join(GRADES_LIST),
                reply_markup=reply_markup
            )
            return GRADES
        else:
            # Go back to previous grade's quantity
            context.user_data['current_grade_index'] -= 1
            grade = context.user_data['pi_data']['grades'][context.user_data['current_grade_index']]
            keyboard = [['⬅️ Back', '❌ Cancel']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(f"📏 Grade: {grade}\nEnter quantity in m³:", reply_markup=reply_markup)
            return QUANTITY
    
    grade = context.user_data['pi_data']['grades'][context.user_data['current_grade_index']]
    try:
        price_value = float(update.message.text.replace(',', ''))
        if price_value < 0: raise ValueError()
        context.user_data['pi_data']['unit_price'][grade] = price_value
    except ValueError:
        keyboard = [['⬅️ Back', '❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"❌ Enter valid price for {grade}:", reply_markup=reply_markup)
        return PRICE
    
    keyboard = [['⬅️ Back', '❌ Cancel']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f"📏 Grade: {grade}\nEnter quantity in m³:", reply_markup=reply_markup)
    return QUANTITY

async def quantity(update: Update, context: CallbackContext):
    if update.message.text == '❌ Cancel':
        return await cancel(update, context)
    
    if update.message.text == '⬅️ Back':
        # Go back to price input for current grade
        grade = context.user_data['pi_data']['grades'][context.user_data['current_grade_index']]
        keyboard = [['⬅️ Back', '❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"💵 Grade: {grade}\nEnter price per m³:", reply_markup=reply_markup)
        return PRICE
    
    grade = context.user_data['pi_data']['grades'][context.user_data['current_grade_index']]
    try:
        quantity_value = float(update.message.text.replace(',', ''))
        if quantity_value < 0: raise ValueError()
        context.user_data['pi_data']['quantity'][grade] = quantity_value
    except ValueError:
        keyboard = [['⬅️ Back', '❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"❌ Enter valid quantity for {grade}:", reply_markup=reply_markup)
        return QUANTITY

    context.user_data['current_grade_index'] += 1
    if context.user_data['current_grade_index'] < len(context.user_data['pi_data']['grades']):
        next_grade = context.user_data['pi_data']['grades'][context.user_data['current_grade_index']]
        keyboard = [['⬅️ Back', '❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"💵 Grade: {next_grade}\nEnter price per m³:", reply_markup=reply_markup)
        return PRICE
    else:
        keyboard = [EXTRAS_LIST]
        keyboard.append(['⬅️ Back', '❌ Cancel'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("🧰 Select extra services (comma separated) or 'None':", reply_markup=reply_markup)
        return EXTRAS

async def extras(update: Update, context: CallbackContext):
    if update.message.text == '❌ Cancel':
        return await cancel(update, context)
    
    if update.message.text == '⬅️ Back':
        # Go back to last grade's quantity
        context.user_data['current_grade_index'] = len(context.user_data['pi_data']['grades']) - 1
        grade = context.user_data['pi_data']['grades'][context.user_data['current_grade_index']]
        keyboard = [['⬅️ Back', '❌ Cancel']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"📏 Grade: {grade}\nEnter quantity in m³:", reply_markup=reply_markup)
        return QUANTITY
    
    extras_text = update.message.text.strip()
    if extras_text.lower() == 'none':
        context.user_data['pi_data']['extras'] = 'None'
    else:
        extras_list = [e.strip() for e in extras_text.split(',') if e.strip().lower() != 'none']
        context.user_data['pi_data']['extras'] = ', '.join(extras_list) if extras_list else 'None'

    pi_data = context.user_data['pi_data']
    total_quantity = sum(pi_data['quantity'][g] for g in pi_data['grades'])
    subtotal = sum(pi_data['unit_price'][g] * pi_data['quantity'][g] for g in pi_data['grades'])
    vat_amount = subtotal * 0.15
    total_amount = subtotal + vat_amount

    grades_summary = "\n".join([f"• {g}: {pi_data['unit_price'][g]:,.2f} × {pi_data['quantity'][g]:,.2f}m³ = {pi_data['unit_price'][g]*pi_data['quantity'][g]:,.2f}" for g in pi_data['grades']])
    draft = (
        f"📋 *DRAFT QUOTE*\n\n👤 Customer: {pi_data['customer']}\n📍 Location: {pi_data['location']}\n📊 Total Quantity: {total_quantity:,.2f}m³\n\n"
        f"🧱 Grades & Pricing:\n{grades_summary}\n\n"
        f"💰 Subtotal: {subtotal:,.2f} Birr\n"
        f"📊 VAT (15%): {vat_amount:,.2f} Birr\n"
        f"💵 *Grand Total: {total_amount:,.2f} Birr*\n\n"
        f"🧰 Extras: {pi_data['extras']}"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Submit", callback_data='confirm_yes')],
        [InlineKeyboardButton("⬅️ Back", callback_data='confirm_back'), InlineKeyboardButton("❌ Cancel", callback_data='confirm_no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(draft, reply_markup=reply_markup, parse_mode='Markdown', reply_markup_remove=ReplyKeyboardRemove())
    return CONFIRM

async def confirm(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == 'confirm_back':
        # Go back to extras selection
        keyboard = [EXTRAS_LIST]
        keyboard.append(['⬅️ Back', '❌ Cancel'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await query.message.reply_text("🧰 Select extra services (comma separated) or 'None':", reply_markup=reply_markup)
        return EXTRAS

    if query.data == 'confirm_yes':
        global bot_data
        bot_data['quote_counter'] += 1
        quote_number = f"RMX-{bot_data['quote_counter']:04d}"
        pi_data = context.user_data['pi_data']
        pi_data['quote_number'] = quote_number
        pi_data['status'] = 'pending'
        bot_data['quotes'][quote_number] = pi_data
        save_data(bot_data)
        
        subtotal = sum(pi_data['unit_price'][g]*pi_data['quantity'][g] for g in pi_data['grades'])
        vat = subtotal * 0.15
        grand_total = subtotal + vat
        
        await query.edit_message_text(
            f"✅ Quote submitted\n"
            f"Quote No: {quote_number}\n"
            f"Customer: {pi_data['customer']}\n"
            f"Subtotal: {subtotal:,.2f} Birr\n"
            f"VAT (15%): {vat:,.2f} Birr\n"
            f"Grand Total: {grand_total:,.2f} Birr"
        )
        await notify_admins(context, quote_number, pi_data)
        return ConversationHandler.END
    else:
        await query.edit_message_text("❌ PI creation cancelled. Use /createpi to start again.")
        return ConversationHandler.END

async def notify_admins(context: CallbackContext, quote_number: str, pi_data: dict):
    subtotal = sum(pi_data['unit_price'][g] * pi_data['quantity'][g] for g in pi_data['grades'])
    vat = subtotal * 0.15
    grand_total = subtotal + vat
    grades_summary = "\n".join([f"• {g}: {pi_data['unit_price'][g]:,.2f} × {pi_data['quantity'][g]:,.2f}m³" for g in pi_data['grades']])
    admin_message = (
        f"🔔 NEW QUOTE\n"
        f"Quote: {quote_number}\n"
        f"Customer: {pi_data['customer']}\n"
        f"Grades:\n{grades_summary}\n"
        f"Subtotal: {subtotal:,.2f} Birr\n"
        f"VAT (15%): {vat:,.2f} Birr\n"
        f"Grand Total: {grand_total:,.2f} Birr\n"
        f"Extras: {pi_data['extras']}"
    )
    keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f'approve_{quote_number}'), InlineKeyboardButton("❌ Reject", callback_data=f'reject_{quote_number}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, reply_markup=reply_markup)
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

async def handle_approval(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Not authorized.", show_alert=True)
        return
    action, quote_number = query.data.split('_', 1)
    if quote_number not in bot_data['quotes']:
        await query.edit_message_text("❌ Quote not found.")
        return
    pi_data = bot_data['quotes'][quote_number]
    if action == 'approve':
        pi_data['status'] = 'approved'
        pi_data['approved_by'] = update.effective_user.username or update.effective_user.first_name
        pi_data['approved_at'] = datetime.now().isoformat()
        save_data(bot_data)
        await query.edit_message_text(f"{query.message.text}\n✅ APPROVED by @{pi_data['approved_by']}")
        pdf_buffer = generate_pdf(pi_data)
        try:
            # Add "Start Over" button after PDF is sent
            keyboard = [[InlineKeyboardButton("🔄 Create New Quote", callback_data='start_over')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_document(
                chat_id=pi_data['user_id'], 
                document=pdf_buffer, 
                filename=f"Quote_{quote_number}.pdf", 
                caption=f"✅ Quote Approved\nQuote No: {quote_number}\n\nClick below to create a new quote:",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Failed to send PDF to user: {e}")
    elif action == 'reject':
        pi_data['status'] = 'rejected'
        pi_data['rejected_by'] = update.effective_user.username or update.effective_user.first_name
        pi_data['rejected_at'] = datetime.now().isoformat()
        save_data(bot_data)
        await query.edit_message_text(f"{query.message.text}\n❌ REJECTED by @{pi_data['rejected_by']}")
        try:
            # Add "Start Over" button after rejection
            keyboard = [[InlineKeyboardButton("🔄 Create New Quote", callback_data='start_over')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=pi_data['user_id'], 
                text=f"❌ Your quote {quote_number} was rejected.\n\nClick below to create a new quote:",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Failed to notify user: {e}")

async def handle_start_over(update: Update, context: CallbackContext):
    """Handle the start over button click"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    context.user_data['pi_data'] = {
        'user_id': update.effective_user.id,
        'username': update.effective_user.username or update.effective_user.first_name,
        'created_at': datetime.now().isoformat()
    }
    keyboard = [['❌ Cancel']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await query.message.reply_text("👤 Enter customer/company name:", reply_markup=reply_markup)
    return CUSTOMER

async def myquotes(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_quotes = [q for q in bot_data['quotes'].values() if q['user_id'] == user_id]
    if not user_quotes:
        await update.message.reply_text("You have no quotes yet.")
        return
    for pi in user_quotes:
        subtotal = sum(pi['unit_price'][g] * pi['quantity'][g] for g in pi['grades'])
        vat = subtotal * 0.15
        grand_total = subtotal + vat
        await update.message.reply_text(
            f"Quote: {pi['quote_number']}\n"
            f"Customer: {pi['customer']}\n"
            f"Subtotal: {subtotal:,.2f} Birr\n"
            f"VAT (15%): {vat:,.2f} Birr\n"
            f"Grand Total: {grand_total:,.2f} Birr\n"
            f"Status: {pi['status']}"
        )

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("❌ Operation cancelled. Use /createpi to start again.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    print("Starting bot initialization...")
    try:
        # Bot token
        application = Application.builder().token("8513160001:AAELK8YtZxL34U2tWrNsXLOGooJEVSWqKWI").build()
        print("Application built successfully!")

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('createpi', create_pi), CallbackQueryHandler(handle_start_over, pattern='^start_over
    )],
            states={
                CUSTOMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, customer_name)],
                LOCATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_input)],
                GRADES: [MessageHandler(filters.TEXT & ~filters.COMMAND, grades)],
                PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price)],
                QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity)],
                EXTRAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, extras)],
                CONFIRM: [CallbackQueryHandler(confirm)]
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            per_message=False
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('myquotes', myquotes))
        application.add_handler(CallbackQueryHandler(handle_approval, pattern='^(approve|reject)_'))
        
        print("✅ Bot started successfully!")
        print("🤖 Bot is running... Press Ctrl+C to stop.")
        application.run_polling()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
