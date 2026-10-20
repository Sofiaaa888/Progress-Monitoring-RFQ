-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Sep 09, 2026 at 03:34 AM
-- Server version: 10.4.32-MariaDB-log
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `monitoring progress rfq`
--

-- --------------------------------------------------------

--
-- Table structure for table `customers`
--

CREATE TABLE `customers` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `customers`
--

INSERT INTO `customers` (`id`, `name`) VALUES
(5, 'PT TMMIN');

-- --------------------------------------------------------

--
-- Table structure for table `model_partlists`
--

CREATE TABLE `model_partlists` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  `model_name` varchar(255) NOT NULL,
  `category` varchar(50) NOT NULL,
  `year` int(11) NOT NULL,
  `partlist_status` varchar(30) DEFAULT 'Open',
  `partlist_done` int(11) DEFAULT 0,
  `partlist_total` int(11) DEFAULT 1,
  `partlist_note` text DEFAULT NULL,
  `created_at` varchar(30) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `model_partlist_files`
--

CREATE TABLE `model_partlist_files` (
  `id` int(11) NOT NULL,
  `model_partlist_id` int(11) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `approval_status` varchar(30) DEFAULT 'Belum Approval',
  `uploaded_by` varchar(100) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `created_at` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `notes`
--

CREATE TABLE `notes` (
  `id` int(11) NOT NULL,
  `part_id` int(11) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `author` varchar(100) NOT NULL,
  `text` text NOT NULL,
  `created_at` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `parts`
--

CREATE TABLE `parts` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  `model_name` varchar(255) NOT NULL,
  `category` varchar(50) NOT NULL,
  `year` int(11) NOT NULL,
  `month` varchar(20) NOT NULL,
  `part_no` varchar(100) NOT NULL,
  `due_date` varchar(10) DEFAULT '',
  `redraw_status` varchar(30) DEFAULT 'Open',
  `redraw_done` int(11) DEFAULT 0,
  `redraw_total` int(11) DEFAULT 1,
  `finish_good` varchar(50) DEFAULT '',
  `komponen` varchar(50) DEFAULT '',
  `drawing_tooling` varchar(50) DEFAULT '',
  `drawing_pipa` varchar(50) DEFAULT '',
  `redraw_note` text DEFAULT NULL,
  `review_status` varchar(30) DEFAULT 'Open',
  `review_done` int(11) DEFAULT 0,
  `review_total` int(11) DEFAULT 1,
  `partlist_status` varchar(30) DEFAULT 'Open',
  `partlist_done` int(11) DEFAULT 0,
  `partlist_total` int(11) DEFAULT 1,
  `partlist_note` text DEFAULT NULL,
  `quick_note` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `redraw_files`
--

CREATE TABLE `redraw_files` (
  `id` int(11) NOT NULL,
  `part_id` int(11) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `approval_status` varchar(30) DEFAULT 'Belum Approval',
  `uploaded_by` varchar(100) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `created_at` varchar(30) NOT NULL,
  `progress_type` varchar(50) DEFAULT 'Finish Good',
  `display_filename` varchar(255) DEFAULT 'Finish Good'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `submissions`
--

CREATE TABLE `submissions` (
  `id` int(11) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `customer` varchar(255) DEFAULT '',
  `model_name` varchar(255) DEFAULT '',
  `partnumber` varchar(100) DEFAULT '',
  `category` varchar(50) DEFAULT 'Chassis',
  `year` int(11) DEFAULT NULL,
  `kondisi` varchar(20) DEFAULT '',
  `due_date` varchar(10) DEFAULT '',
  `part_id` int(11) DEFAULT NULL,
  `item_name` varchar(255) DEFAULT '',
  `included_items` text DEFAULT NULL,
  `marketing_note` text DEFAULT NULL,
  `uploaded_by` varchar(100) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `created_at` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `management_judgements`
--

CREATE TABLE IF NOT EXISTS `management_judgements` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `jenis` varchar(50) NOT NULL,
  `customer` varchar(255) DEFAULT '',
  `commodity` varchar(255) DEFAULT '',
  `model_name` varchar(255) DEFAULT '',
  `partnumber` varchar(100) DEFAULT '',
  `keputusan` varchar(50) NOT NULL,
  `catatan` text NOT NULL,
  `author` varchar(100) NOT NULL,
  `recipient_divisions` varchar(255) DEFAULT '',
  `email_sent` tinyint(4) DEFAULT 0,
  `created_at` varchar(30) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `rfq_notes`
--

CREATE TABLE IF NOT EXISTS `rfq_notes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `divisi` varchar(50) NOT NULL,
  `author` varchar(100) NOT NULL,
  `customer` varchar(255) DEFAULT '',
  `model_name` varchar(255) DEFAULT '',
  `partnumber` varchar(100) DEFAULT '',
  `category` varchar(50) DEFAULT '',
  `text` text NOT NULL,
  `recipient_divisions` varchar(255) DEFAULT '',
  `email_sent` tinyint(4) DEFAULT 0,
  `created_at` varchar(30) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `divisi` varchar(50) NOT NULL,
  `email` varchar(255) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `username`, `password`, `divisi`, `email`) VALUES
(1, 'marketing1', 'scrypt:32768:8:1$gX8e8yWQ1eJUwEar$d1d41716609ce57bd903e631014cf3d7abb5a8571b1708f586747883964b866937c4db7982d2703f1672ced05982077956007ca67aaf8577ee890560120136ed', 'Marketing', ''),
(2, 'engineer1', 'scrypt:32768:8:1$6nX7dqwO4hMbw13z$6cd8bf24f3521886186f6594e6167c127dc8d29fa5418e3db1a134c8d83ee22897f058c016acee2a7e9e8076c56b7cffe3b17dc031859f761c6d5cb54e241c4c', 'Engineer', ''),
(3, 'purchasing1', 'scrypt:32768:8:1$GVTR4cBnFUQvVly3$26acc5c59196016a8efadd6efe72e7e75833fbeacd042e494f0e89ebe4e8d9e94fb33839d65709df7009149056bbe3117605a7d987ce90e6fc4905f332fab072', 'Purchasing', ''),
(4, 'management1', 'scrypt:32768:8:1$jDYWAuqYwe5Ise6u$868f5238c58ceb88f4ac0ca4f3cfc9ba1876cbcadb7edcd8aa4a9ee925f28529b24c9a0c1eae543e817fd38718bd3eb15d39662a29d473398cb3bfe179b77777', 'Management', ''),
(5, 'admin', 'scrypt:32768:8:1$WFbwigpVXl7gJSBy$27c5c270d2036967ad679b8ff295219df374c22f37ebe436b8259d0c11203c6bde82fde1bd85d0c6bfa57c9b0ead76a5a16cfad7be99ac25ab47d2703b5b08d1', 'Admin', '');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `customers`
--
ALTER TABLE `customers`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_customer_name` (`name`);

--
-- Indexes for table `model_partlists`
--
ALTER TABLE `model_partlists`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_model_partlist` (`customer_id`,`model_name`,`category`,`year`),
  ADD KEY `idx_model_partlists_customer` (`customer_id`);

--
-- Indexes for table `model_partlist_files`
--
ALTER TABLE `model_partlist_files`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_model_partlist_files_model` (`model_partlist_id`);

--
-- Indexes for table `notes`
--
ALTER TABLE `notes`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_notes_part` (`part_id`);

--
-- Indexes for table `parts`
--
ALTER TABLE `parts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_parts_customer` (`customer_id`);

--
-- Indexes for table `redraw_files`
--
ALTER TABLE `redraw_files`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_redraw_files_part` (`part_id`);

--
-- Indexes for table `submissions`
--
ALTER TABLE `submissions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_submissions_part` (`part_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_user_divisi` (`username`,`divisi`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `customers`
--
ALTER TABLE `customers`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `model_partlists`
--
ALTER TABLE `model_partlists`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `model_partlist_files`
--
ALTER TABLE `model_partlist_files`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `notes`
--
ALTER TABLE `notes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `parts`
--
ALTER TABLE `parts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `redraw_files`
--
ALTER TABLE `redraw_files`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `submissions`
--
ALTER TABLE `submissions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `model_partlists`
--
ALTER TABLE `model_partlists`
  ADD CONSTRAINT `fk_model_partlists_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `model_partlist_files`
--
ALTER TABLE `model_partlist_files`
  ADD CONSTRAINT `fk_model_partlist_files_model` FOREIGN KEY (`model_partlist_id`) REFERENCES `model_partlists` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `notes`
--
ALTER TABLE `notes`
  ADD CONSTRAINT `fk_notes_part` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `parts`
--
ALTER TABLE `parts`
  ADD CONSTRAINT `fk_parts_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `redraw_files`
--
ALTER TABLE `redraw_files`
  ADD CONSTRAINT `fk_redraw_files_part` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `submissions`
--
ALTER TABLE `submissions`
  ADD CONSTRAINT `fk_submissions_part` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
COMMIT;
ALTER TABLE submissions 
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
