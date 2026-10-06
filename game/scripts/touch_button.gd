class_name TouchButton
extends TouchScreenButton
## Dumaloq sensorli tugma. Input action'ni bosadi, shuning uchun klaviatura
## bilan bir xil ishlaydi va bir vaqtda bir nechta tugma bosilishi mumkin.

var label := ""
var radius := 52.0
var color := Color(0.85, 0.15, 0.15)


func setup(p_action: String, p_label: String, p_radius: float, p_color: Color) -> void:
	action = p_action
	label = p_label
	radius = p_radius
	color = p_color
	var s := CircleShape2D.new()
	s.radius = p_radius
	shape = s
	passby_press = false
	queue_redraw()


func _ready() -> void:
	pressed.connect(queue_redraw)
	released.connect(queue_redraw)


func _draw() -> void:
	var down := is_pressed()
	var c := color.lightened(0.25) if down else color
	c.a = 0.75 if down else 0.5
	draw_circle(Vector2.ZERO, radius, c)
	draw_arc(Vector2.ZERO, radius, 0, TAU, 40, Color(1, 1, 1, 0.6), 3.0)
	var font := ThemeDB.fallback_font
	var lines := label.split("\n")
	var fs := 20 if radius >= 50 else 17
	var line_h := fs + 2.0
	var y0 := -line_h * (lines.size() - 1) / 2.0 + fs * 0.35
	for i in lines.size():
		draw_string(font, Vector2(-radius, y0 + i * line_h), lines[i],
			HORIZONTAL_ALIGNMENT_CENTER, radius * 2.0, fs, Color.WHITE)
