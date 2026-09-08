import pytest

from getpass_core.crop import compute_crop_box

CANVAS = (700, 700)
FRAME_H = int(700 * 0.88)
FRAME_W = int(FRAME_H * 3 / 4)
FRAME = ((700 - FRAME_W) // 2, (700 - FRAME_H) // 2, FRAME_W, FRAME_H)


def state(scale, base, dx=0, dy=0):
    return {"scale": scale, "offset_x": dx, "offset_y": dy, "base_scale": base}


@pytest.mark.parametrize("size", [(4000, 3000), (1200, 1600), (2000, 2000),
                                  (600, 4000), (5000, 1000)])
@pytest.mark.parametrize("scale", [0.25, 0.6, 1.0, 2.0, 6.0])
def test_crop_always_three_by_four(size, scale):
    ow, oh = size
    base = max(FRAME_W / ow, FRAME_H / oh)
    rx, ry, rw, rh = compute_crop_box(ow, oh, state(scale, base), FRAME, CANVAS)
    assert abs(rw / rh - 0.75) < 0.02, f"кадр {rw}x{rh} не 3:4"


@pytest.mark.parametrize("size", [(4000, 3000), (1200, 1600), (600, 4000)])
@pytest.mark.parametrize("dx,dy", [(0, 0), (500, 500), (-800, -800), (2000, -2000)])
def test_crop_stays_inside_image(size, dx, dy):
    ow, oh = size
    base = max(FRAME_W / ow, FRAME_H / oh)
    rx, ry, rw, rh = compute_crop_box(ow, oh, state(1.0, base, dx, dy), FRAME, CANVAS)
    assert 0 <= rx and 0 <= ry
    assert rx + rw <= ow and ry + rh <= oh
    assert rw > 0 and rh > 0


def test_zoom_in_shrinks_crop():
    ow, oh = 4000, 3000
    base = max(FRAME_W / ow, FRAME_H / oh)
    _, _, w1, _ = compute_crop_box(ow, oh, state(1.0, base), FRAME, CANVAS)
    _, _, w2, _ = compute_crop_box(ow, oh, state(3.0, base), FRAME, CANVAS)
    assert w2 < w1
