extends SceneTree
## Bir necha kadr o'ynab, ekran rasmini saqlaydi (vizual tekshiruv uchun).
##   godot --path game --fixed-fps 60 -s res://tests/screenshot.gd -- <chiqish_papka>

var main: Node
var frames := 0
var out_dir := "user://"
var shots := {90: "intro", 200: "fight1", 260: "fight2", 330: "fight3"}


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out_dir = args[0]
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames == 2:
		for c in main.get_children():
			if c is PlayerController:
				c.queue_free()
		var ai := AIController.new()
		ai.fighter = main.player
		ai.difficulty = 0.8
		main.add_child(ai)
	if shots.has(frames):
		var img := root.get_texture().get_image()
		img.save_png(out_dir.path_join("shot_%s.png" % shots[frames]))
	return frames > 340
