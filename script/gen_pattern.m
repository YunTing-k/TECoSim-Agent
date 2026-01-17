%+FHDR//////////////////////////////////////////////////////////////////////////////
% Company: Shanghai Jiao Tong University
% Engineer: Yu Huang
% Coding: UTF-8
% Create Date: 2026.1.13
% Description:
% Generate fixed pattern image from matlab
%
% Revision:
% ---------------------------------------------------------------------------------
% [Date]         [By]         [Version]         [Change Log]
% ---------------------------------------------------------------------------------
% 2026/1/13      Yu Huang     1.0               First implementation
% ---------------------------------------------------------------------------------
%
%-FHDR//////////////////////////////////////////////////////////////////////////////
clc
clear
close all
%% Params
width = 1920;
height = 1080;
img = zeros(height, width, 3, 'uint8');
idx = 1;
%% Pure RGB [x x x] with 8 cases
for i = 0:7
    rgb_select = dec2bin(i,3);
    img(:,:,1) = 255 * str2double(rgb_select(1));
    img(:,:,2) = 255 * str2double(rgb_select(2));
    img(:,:,3) = 255 * str2double(rgb_select(3));
    imwrite(img, [num2str(idx), '.png']);
    idx = idx + 1;
end
%% | - / \ Pattern with 8 cases
% | pattern 1
img = zeros(height, width, 3, 'uint8');
img(:,1:width/2,1) = 255;
img(:,1:width/2,2) = 255;
img(:,1:width/2,3) = 255;
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% | pattern 2
img = zeros(height, width, 3, 'uint8') + 255;
img(:,1:width/2,1) = 0;
img(:,1:width/2,2) = 0;
img(:,1:width/2,3) = 0;
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% - pattern 1
img = zeros(height, width, 3, 'uint8');
img(1:height/2,:,1) = 255;
img(1:height/2,:,2) = 255;
img(1:height/2,:,3) = 255;
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% - pattern 2
img = zeros(height, width, 3, 'uint8') + 255;
img(1:height/2,:,1) = 0;
img(1:height/2,:,2) = 0;
img(1:height/2,:,3) = 0;
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% / pattern 1
img = zeros(height, width, 3, 'uint8') + 255;
for i = 1:height
    for j = 1:width
        if (i <= (height - (height-1) * j / width))
            img(i,j,:) = 0;
        end
    end
end
img = flipud(img);
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% / pattern 2
img = zeros(height, width, 3, 'uint8');
for i = 1:height
    for j = 1:width
        if (i <= (height - (height-1) * j / width))
            img(i,j,:) = 255;
        end
    end
end
img = flipud(img);
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% \ pattern 1
img = zeros(height, width, 3, 'uint8') + 255;
for i = 1:height
    for j = 1:width
        if (i <= (height - (height-1) * j / width))
            img(i,j,:) = 0;
        end
    end
end
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
% \ pattern 2
img = zeros(height, width, 3, 'uint8');
for i = 1:height
    for j = 1:width
        if (i <= (height - (height-1) * j / width))
            img(i,j,:) = 255;
        end
    end
end
imwrite(img, [num2str(idx), '.png']);
idx = idx + 1;
%% checkerboard pattern
chk_num = 7;
chk_len = 60;
for i = chk_num:-1:1
    chk = checkerboard(chk_len * i, round(height / 2 / chk_len / i) + 1, round(width / 2 / chk_len / i) + 1);
    chk = uint8(255 * (chk > 0.5));
    chk = chk(1:height, 1:width);
    img(:,:,1) = chk;
    img(:,:,2) = chk;
    img(:,:,3) = chk;
    imwrite(img, [num2str(idx), '.png']);
    idx = idx + 1;

    chk = 255 - chk;
    img(:,:,1) = chk;
    img(:,:,2) = chk;
    img(:,:,3) = chk;
    imwrite(img, [num2str(idx), '.png']);
    idx = idx + 1;
end
