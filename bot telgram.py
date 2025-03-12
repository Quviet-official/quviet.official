import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import datetime
import random
import os

# Lưu trữ dữ liệu giao dịch
transactions = []
balance = 0
daily_threshold = None
monthly_threshold = None

# Hàm tạo mã ID ngẫu nhiên
def generate_transaction_id():
    return ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=6))

# Hàm phân tích và phân loại giao dịch
def parse_transaction(text):
    global balance
    today = datetime.datetime.now()
    date = today

    # Xử lý ngày tháng nếu có
    parts = text.split()
    if len(parts) > 0 and '/' in parts[0]:
        day, month = map(int, parts[0].split('/'))
        date = datetime.datetime(2025, month, day)
        parts = parts[1:]
    
    # Xử lý số tiền
    amount_str = parts[0]
    amount = 0
    if 'm' in amount_str.lower():
        amount = int(float(amount_str.lower().replace('m', '').replace('+', '').replace('-', '')) * 1000000)
    elif 'k' in amount_str.lower():
        amount = int(float(amount_str.lower().replace('k', '').replace('+', '').replace('-', '')) * 1000)
    
    if amount_str.startswith('-'):
        amount = -amount
    
    # Cập nhật số dư
    balance += amount

    # Phân loại giao dịch (giả lập thay vì dùng Gemini)
    content = ' '.join(parts[1:]).lower()
    category = "Khác"
    if "lương" in content:
        category = "Thu Nhập"
    elif "cf" in content or "cà phê" in content or "ăn" in content:
        category = "Ăn Uống"
    elif "mua" in content:
        category = "Mua Sắm"

    # Tạo giao dịch
    transaction = {
        "id": generate_transaction_id(),
        "date": date,
        "amount": amount,
        "balance": balance,
        "category": category,
        "content": content
    }
    transactions.append(transaction)
    return transaction

# Hàm gửi thông tin giao dịch
def send_transaction_info(update, transaction):
    weekday = transaction["date"].strftime("%A")
    date_str = transaction["date"].strftime("%d/%m/%Y")
    reply = f"📅 {weekday} Ngày {date_str}\n" \
            f"🆔 Mã ID Giao Dịch: {transaction['id']}\n" \
            f"💰 Số tiền GD: {transaction['amount']:,} ₫\n" \
            f"💵 Số dư: {transaction['balance']:,} ₫\n" \
            f"📌 Phân Loại: {transaction['category']}\n" \
            f"✍️ Nội Dung: {transaction['content']}"
    update.message.reply_text(reply)

# Xử lý tin nhắn giao dịch
def handle_transaction(update, context):
    text = update.message.text
    transaction = parse_transaction(text)
    send_transaction_info(update, transaction)
    check_threshold(update, context)

# Kiểm tra ngưỡng chi tiêu
def check_threshold(update, context):
    today = datetime.datetime.now()
    daily_spent = sum(-t['amount'] for t in transactions if t['amount'] < 0 and t['date'].date() == today.date())
    monthly_spent = sum(-t['amount'] for t in transactions if t['amount'] < 0 and t['date'].month == today.month and t['date'].year == today.year)
    
    if daily_threshold and daily_spent >= daily_threshold:
        update.message.reply_text(f"⚠️ Cảnh báo: Bạn đã chi {daily_spent:,} ₫ trong ngày, vượt ngưỡng {daily_threshold:,} ₫!")
    if monthly_threshold and monthly_spent >= monthly_threshold:
        update.message.reply_text(f"⚠️ Cảnh báo: Bạn đã chi {monthly_spent:,} ₫ trong tháng, vượt ngưỡng {monthly_threshold:,} ₫!")

# Lệnh /ds - Danh sách giao dịch
def list_transactions(update, context):
    keyboard = [
        [InlineKeyboardButton("Xem theo ngày", callback_data='day'),
         InlineKeyboardButton("Xem theo tháng", callback_data='month'),
         InlineKeyboardButton("Xem theo năm", callback_data='year')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Chọn cách xem danh sách giao dịch:', reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'day':
        query.edit_message_text(text="Nhập ngày (VD: /ds 05/03):")
    elif query.data == 'month':
        query.edit_message_text(text="Nhập tháng (VD: /ds 02):")
    elif query.data == 'year':
        query.edit_message_text(text="Nhập năm (VD: /ds 2025):")

def detailed_list(update, context):
    args = context.args
    if not args:
        update.message.reply_text("Vui lòng nhập định dạng đúng, VD: /ds 05/03 hoặc /ds 02")
        return
    
    filter_str = args[0]
    if '/' in filter_str:
        day, month = map(int, filter_str.split('/'))
        filtered = [t for t in transactions if t['date'].day == day and t['date'].month == month]
        title = f"Danh sách giao dịch ngày {filter_str}"
    elif len(filter_str) == 2:
        month = int(filter_str)
        filtered = [t for t in transactions if t['date'].month == month]
        title = f"Danh sách giao dịch tháng {filter_str}"
    else:
        year = int(filter_str)
        filtered = [t for t in transactions if t['date'].year == year]
        title = f"Danh sách giao dịch năm {filter_str}"

    if not filtered:
        update.message.reply_text(f"Không có giao dịch nào trong {title.lower()}!")
        return
    
    reply = f"==== {title} ====\n"
    for t in filtered:
        reply += f"📅 {t['date'].strftime('%A %d/%m/%Y')}\n" \
                 f"🆔 {t['id']} | 💰 {t['amount']:,} ₫ | 💵 {t['balance']:,} ₫\n" \
                 f"📌 {t['category']} | ✍️ {t['content']}\n" \
                 f"-----\n"
    update.message.reply_text(reply)

# Lệnh /xoa - Xóa giao dịch
def delete_transaction(update, context):
    if not context.args:
        update.message.reply_text("Vui lòng cung cấp mã ID giao dịch! VD: /xoa ABC123")
        return
    trans_id = context.args[0]
    global balance, transactions
    for i, t in enumerate(transactions):
        if t['id'] == trans_id:
            balance -= t['amount']
            del transactions[i]
            update.message.reply_text(f"✅ Đã xóa giao dịch {trans_id}")
            return
    update.message.reply_text(f"❌ Không tìm thấy giao dịch với mã {trans_id}")

# Lệnh /xoaall - Xóa toàn bộ
def delete_all(update, context):
    global transactions, balance
    transactions = []
    balance = 0
    update.message.reply_text("🗑️ Đã xóa toàn bộ giao dịch!")

# Lệnh /nguong - Thiết lập ngưỡng
def set_threshold(update, context):
    global daily_threshold, monthly_threshold
    if not context.args:
        update.message.reply_text("VD: /nguongn 500k (ngưỡng ngày) hoặc /nguongt 3m (ngưỡng tháng)")
        return
    
    threshold_str = context.args[0]
    if threshold_str.startswith('n'):
        amount = threshold_str[1:]
        if 'm' in amount:
            daily_threshold = int(float(amount.replace('m', '')) * 1000000)
        elif 'k' in amount:
            daily_threshold = int(float(amount.replace('k', '')) * 1000)
        update.message.reply_text(f"✅ Ngưỡng chi tiêu ngày: {daily_threshold:,} ₫")
    elif threshold_str.startswith('t'):
        amount = threshold_str[1:]
        if 'm' in amount:
            monthly_threshold = int(float(amount.replace('m', '')) * 1000000)
        elif 'k' in amount:
            monthly_threshold = int(float(amount.replace('k', '')) * 1000)
        update.message.reply_text(f"✅ Ngưỡng chi tiêu tháng: {monthly_threshold:,} ₫")
    else:
        update.message.reply_text("Sai định dạng! VD: /nguongn 500k hoặc /nguongt 3m")

# Lệnh /xuatbaocao - Xuất báo cáo
def export_report(update, context):
    args = context.args
    today = datetime.datetime.now()
    if not args:
        filtered = transactions
        filename = f"baocao_{today.strftime('%d%m%Y')}.txt"
    elif args[0].startswith('n') and '/' in args[0]:
        day, month = map(int, args[0][1:].split('/'))
        filtered = [t for t in transactions if t['date'].day == day and t['date'].month == month]
        filename = f"baocao_ngay_{day:02d}{month:02d}.txt"
    elif args[0].startswith('t'):
        month = int(args[0][1:]) if len(args[0]) > 1 else today.month
        filtered = [t for t in transactions if t['date'].month == month]
        filename = f"baocao_thang_{month:02d}.txt"
    elif args[0].startswith('nam'):
        year = int(args[0][3:]) if len(args[0]) > 3 else today.year
        filtered = [t for t in transactions if t['date'].year == year]
        filename = f"baocao_nam_{year}.txt"
    else:
        filtered = transactions
        filename = f"baocao_{today.strftime('%d%m%Y')}.txt"

    if not filtered:
        update.message.reply_text("Không có giao dịch để xuất báo cáo!")
        return
    
    report = f"==== Báo cáo giao dịch ====\n"
    for t in filtered:
        report += f"📅 {t['date'].strftime('%A %d/%m/%Y')}\n" \
                  f"🆔 {t['id']} | 💰 {t['amount']:,} ₫ | 💵 {t['balance']:,} ₫\n" \
                  f"📌 {t['category']} | ✍️ {t['content']}\n" \
                  f"-----\n"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    with open(filename, 'rb') as f:
        update.message.reply_document(document=f, filename=filename)
    os.remove(filename)

# Khởi động bot
def main():
    updater = Updater("7572640566:AAGQ-y1om1tXTQ1qQjr7nT-5z2lo9NjEHL4", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("ds", list_transactions))
    dp.add_handler(CommandHandler("ds", detailed_list, pass_args=True))
    dp.add_handler(CommandHandler("xoa", delete_transaction, pass_args=True))
    dp.add_handler(CommandHandler("xoaall", delete_all))
    dp.add_handler(CommandHandler("nguong", set_threshold, pass_args=True))
    dp.add_handler(CommandHandler("xuatbaocao", export_report, pass_args=True))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_transaction))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()