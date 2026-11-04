"""Launch BNO085-only preview/controller; no image rotation estimator."""
import sys
from imu_trial import main

if __name__ == '__main__':
    sys.argv[1:1] = ['--sensor', 'bno085']
    main()
