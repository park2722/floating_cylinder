import cv2 as cv
import numpy as np

# hw3에서 사용한 select_img과 calib_camera_from_chessboard 함수를 그대로 가져와서 사용합니다.
def select_img(video_file, board_pattern, select_all=False, wait_msec=10):
    video = cv.VideoCapture(video_file)
    img_list = []

    if not video.isOpened():
        print("비디오 파일을 열 수 없습니다.")
        return img_list

    # 1. 영상의 고유 FPS (초당 프레임 수) 가져오기
    fps = video.get(cv.CAP_PROP_FPS)
    
    # 2. wait_msec 시간 간격을 프레임 개수로 변환하기
    skip_frames = int(fps * (wait_msec / 1000.0))
    
    # 만약 입력한 대기 시간이 너무 짧아서 건너뛸 프레임이 0이 되면, 최소 1프레임씩(매 프레임) 추출
    if skip_frames < 1:
        skip_frames = 1

    frame_count = 0

    while True:
        # 영상은 무조건 순서대로 정상 속도로 읽어옴
        ret, frame = video.read()
        
        if not ret:
            break
            
        # 3. 현재 프레임 번호가 skip_frames의 배수일 때만 리스트에 담기
        if frame_count % skip_frames == 0:
            img_list.append(frame)
            
        frame_count += 1

    video.release()
    print("""총 {}개의 프레임이 추출되었습니다.""".format(len(img_list)))
    return img_list

def calib_camera_from_chessboard(image_list, board_pattern, board_cellsize, K=None, dist_coeffs=None, calib_flags=None):
    print("체스보드 패턴이 감지된 이미지에서 카메라 보정 수행 중...")
    img_points =[]
    for img in image_list:
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        complete, corners = cv.findChessboardCorners(gray, board_pattern)

        if complete:
            img_points.append(corners)
    assert  len(img_points) > 0, "체스보드 패턴이 감지된 이미지가 없습니다." #조건이 참이 아니면 AssertionError 예외 발생

    obj_pts = [[c,r,0] for r in range(board_pattern[1]) for c in range(board_pattern[0])]
    obj_points = [np.array(obj_pts, dtype=np.float32) * board_cellsize] * len(img_points)
    print("calib return sequence")
    return cv.calibrateCamera(obj_points, img_points, gray.shape[::-1], K, dist_coeffs, flags=calib_flags)



def draw_cylinder(img, rvec, tvec, K, dist, board_cellsize, cx=5, cy=4, radius=0.05, height=0.1):
    """
    체스판의 특정 좌표(cx, cy)를 기준으로 원기둥을 그리는 함수
    """
    num_points = 50
    angles = np.linspace(0, 2 * np.pi, num_points)
    
    # 📍 추가된 부분: 체스판 칸 번호(cx, cy)를 실제 3D 물리적 거리로 변환
    offset_x = cx * board_cellsize
    offset_y = cy * board_cellsize
    
    # 📍 수정된 부분: 원 생성 시 중심점(offset)을 더해줍니다.
    bottom_pts = np.array([[offset_x + radius * np.cos(a), offset_y + radius * np.sin(a), 0] for a in angles], dtype=np.float32)
    top_pts = np.array([[offset_x + radius * np.cos(a), offset_y + radius * np.sin(a), -height] for a in angles], dtype=np.float32)
    
    # 2. 3D 점을 2D 이미지 평면으로 투영
    img_pts_bottom, _ = cv.projectPoints(bottom_pts, rvec, tvec, K, dist)
    img_pts_top, _ = cv.projectPoints(top_pts, rvec, tvec, K, dist)
    
    img_pts_bottom = img_pts_bottom.astype(int)
    img_pts_top = img_pts_top.astype(int)
    
    # 3. 원기둥 그리기
    cv.polylines(img, [img_pts_bottom], True, (255, 0, 0), 2)  # 파란색 바닥
    cv.polylines(img, [img_pts_top], True, (0, 255, 0), 2)     # 초록색 뚜껑
    
    for i in range(0, num_points, num_points // 8):
        cv.line(img, tuple(img_pts_bottom[i][0]), tuple(img_pts_top[i][0]), (0, 0, 255), 2)

    return img

def run_ar_session(video_file, board_pattern, board_cellsize, K, dist):
    cap = cv.VideoCapture(video_file)
    
    # 체스판의 실제 3D 좌표 설정
    objp = np.zeros((board_pattern[0] * board_pattern[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_pattern[0], 0:board_pattern[1]].T.reshape(-1, 2)
    objp *= board_cellsize

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        ret_corners, corners = cv.findChessboardCorners(gray, board_pattern)

        if ret_corners:
            # PnP 알고리즘을 사용하여 카메라의 자세(Rotation, Translation) 계산 [cite: 9, 10, 32]
            _, rvec, tvec = cv.solvePnP(objp, corners, K, dist)

            # 계산된 자세를 바탕으로 원기둥 그리기
            frame = draw_cylinder(frame, rvec, tvec, K, dist, board_cellsize, cx=3, cy=4)

        cv.imshow('AR Cylinder Pose Estimation', frame)
        if cv.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv.destroyAllWindows()

if __name__ == "__main__":
    video_file = "undistorted.mp4"
    board_pattern = (10, 7) # 체스보드 패턴의 가로, 세로 코너 수
    board_cellsize = 0.025 # 체스보드 셀의 실제 크기 (단위: 미터)

    # 비디오에서 체스보드 패턴이 감지된 프레임 추출
    img_list = select_img(video_file, board_pattern, select_all=True, wait_msec=500)

    # 카메라 보정 수행
    RMSE, K, dist_coeffs, _, _ = calib_camera_from_chessboard(img_list, board_pattern, board_cellsize)


    # 2. AR 실행 (K와 dist_coeffs가 결정된 후 실행)
    print("AR 시스템을 시작합니다...")
    run_ar_session("undistorted.mp4", (10, 7), 0.025, K, dist_coeffs)