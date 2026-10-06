class_name HUD
extends CanvasLayer
## Ekrandagi interfeys: sog'lik va chidamlilik panellari, raund va taymer,
## markaziy xabarlar, jang oxiridagi oyna hamda sensorli boshqaruv.

signal restart_pressed

## [action, yozuv, rang, ustun (o'ngdan), qator (pastdan), radius]
const BUTTONS := [
	["block",     "BLOK",            Color(0.2, 0.45, 0.85), 0, 0, 62.0],
	["jab",       "JAB",             Color(0.8, 0.15, 0.15), 1, 0, 52.0],
	["cross",     "KROSS",           Color(0.8, 0.15, 0.15), 2, 0, 52.0],
	["dodge",     "QOCHISH",         Color(0.2, 0.6, 0.35),  0, 1, 52.0],
	["hook",      "XUK",             Color(0.8, 0.15, 0.15), 1, 1, 52.0],
	["uppercut",  "APPER-\nKOT",     Color(0.8, 0.15, 0.15), 2, 1, 52.0],
	["high_kick", "BALAND\nTEPKI",   Color(0.85, 0.5, 0.1),  1, 2, 52.0],
	["low_kick",  "PAST\nTEPKI",     Color(0.85, 0.5, 0.1),  2, 2, 52.0],
]

var joystick: VirtualJoystick

var _hp_bars: Array[ProgressBar] = []
var _st_bars: Array[ProgressBar] = []
var _names: Array[Label] = []
var _round_label: Label
var _timer_label: Label
var _message: Label
var _end_panel: PanelContainer
var _end_text: Label
var _buttons: Array[TouchButton] = []
var _top: Control
var _msg_tween: Tween


func _ready() -> void:
	_build_top()
	_build_message()
	_build_end_panel()
	_build_controls()
	get_viewport().size_changed.connect(_layout)
	_layout()


func _build_top() -> void:
	_top = Control.new()
	_top.set_anchors_preset(Control.PRESET_FULL_RECT)
	_top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_top)

	for i in 2:
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 4)
		box.custom_minimum_size = Vector2(420, 0)
		box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_top.add_child(box)

		var name_label := _make_label("", 24)
		name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT if i == 0 else HORIZONTAL_ALIGNMENT_RIGHT
		box.add_child(name_label)
		_names.append(name_label)

		var hp := _make_bar(Color(0.85, 0.15, 0.15), 26, i == 1)
		box.add_child(hp)
		_hp_bars.append(hp)
		var st := _make_bar(Color(0.95, 0.75, 0.15), 12, i == 1)
		box.add_child(st)
		_st_bars.append(st)

	var center := VBoxContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.alignment = BoxContainer.ALIGNMENT_BEGIN
	_top.add_child(center)
	_round_label = _make_label("1-RAUND", 22)
	_round_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	center.add_child(_round_label)
	_timer_label = _make_label("1:30", 40)
	_timer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	center.add_child(_timer_label)


func _build_message() -> void:
	_message = _make_label("", 72)
	_message.set_anchors_preset(Control.PRESET_FULL_RECT)
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_message.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_message.add_theme_color_override("font_outline_color", Color.BLACK)
	_message.add_theme_constant_override("outline_size", 12)
	_message.modulate.a = 0.0
	add_child(_message)


func _build_end_panel() -> void:
	_end_panel = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.05, 0.08, 0.92)
	sb.set_corner_radius_all(16)
	sb.set_content_margin_all(32)
	sb.border_color = Color(0.85, 0.65, 0.15)
	sb.set_border_width_all(3)
	_end_panel.add_theme_stylebox_override("panel", sb)
	_end_panel.visible = false
	add_child(_end_panel)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 24)
	_end_panel.add_child(box)
	_end_text = _make_label("", 34)
	_end_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_end_text)

	var btn := Button.new()
	btn.text = "QAYTA JANG"
	btn.custom_minimum_size = Vector2(320, 80)
	btn.add_theme_font_size_override("font_size", 32)
	btn.pressed.connect(func(): restart_pressed.emit())
	box.add_child(btn)


func _build_controls() -> void:
	joystick = VirtualJoystick.new()
	add_child(joystick)
	for b in BUTTONS:
		var tb := TouchButton.new()
		tb.setup(b[0], b[1], b[5], b[2])
		tb.set_meta("col", b[3])
		tb.set_meta("row", b[4])
		add_child(tb)
		_buttons.append(tb)


func _layout() -> void:
	var size := get_viewport().get_visible_rect().size
	var margin := 24.0
	var boxes := _top.get_children()
	var left := boxes[0] as Control
	var right := boxes[1] as Control
	var center := boxes[2] as Control
	left.position = Vector2(margin, margin)
	right.position = Vector2(size.x - margin - 420, margin)
	center.size = Vector2(200, 80)
	center.position = Vector2(size.x / 2 - 100, margin - 6)

	_end_panel.reset_size()
	_end_panel.position = (size - _end_panel.size) / 2

	joystick.set_rest_position(Vector2(180, size.y - 170))
	joystick.active_max_x = size.x * 0.45
	for tb in _buttons:
		var col: int = tb.get_meta("col")
		var row: int = tb.get_meta("row")
		tb.position = Vector2(size.x - 95 - col * 122, size.y - 95 - row * 122)


func _make_label(text: String, font_size: int) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", 6)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _make_bar(fill: Color, height: float, reverse: bool) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(420, height)
	bar.show_percentage = false
	bar.max_value = 100
	bar.value = 100
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if reverse:
		bar.fill_mode = ProgressBar.FILL_END_TO_BEGIN
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.55)
	bg.set_corner_radius_all(4)
	bg.border_color = Color(1, 1, 1, 0.5)
	bg.set_border_width_all(2)
	var fg := StyleBoxFlat.new()
	fg.bg_color = fill
	fg.set_corner_radius_all(4)
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fg)
	return bar


# ---------------------------------------------------------------------------
# Yangilash
# ---------------------------------------------------------------------------

func set_names(a: String, b: String) -> void:
	_names[0].text = a
	_names[1].text = b


func update_fighters(fighters: Array) -> void:
	for i in 2:
		var f: Fighter = fighters[i]
		_hp_bars[i].value = f.health / f.max_health * 100.0
		_st_bars[i].value = f.stamina / f.max_stamina * 100.0


func set_round(n: int, total: int) -> void:
	_round_label.text = "%d/%d-RAUND" % [n, total]


func set_time(seconds: float) -> void:
	var s := int(ceil(max(seconds, 0.0)))
	_timer_label.text = "%d:%02d" % [s / 60, s % 60]
	_timer_label.modulate = Color(1, 0.3, 0.3) if s <= 10 else Color.WHITE


func show_message(text: String, duration := 1.5, color := Color.WHITE) -> void:
	if _msg_tween:
		_msg_tween.kill()
	_message.text = text
	_message.modulate = color
	_message.scale = Vector2.ONE
	_msg_tween = create_tween()
	_msg_tween.tween_property(_message, "modulate:a", 1.0, 0.15)
	_msg_tween.tween_interval(duration)
	_msg_tween.tween_property(_message, "modulate:a", 0.0, 0.3)


func show_end(text: String) -> void:
	_end_text.text = text
	_end_panel.visible = true
	_layout()
	for tb in _buttons:
		tb.visible = false
	joystick.visible = false
